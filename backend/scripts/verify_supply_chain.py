# Creado por Aldo Garcia.
"""Verificacion de cadena de suministro del arbol de dependencias.

Motivado por los gusanos autopropagables de npm: paquetes comprometidos que
ejecutan codigo en el ciclo de vida de instalacion, roban credenciales del
entorno y republican paquetes del mantenedor afectado.

Comprueba cuatro cosas sobre el arbol REALMENTE instalado, no sobre el
manifiesto declarado:

1. **Lista de bloqueo** -- ningun paquete/version de
   ``config/supply_chain_denylist.yaml`` esta presente, a ninguna profundidad.
2. **Scripts de instalacion** -- ningun paquete declara ``preinstall``,
   ``install`` o ``postinstall``. Es el vector por el que se propaga el gusano.
3. **Indicadores de compromiso** -- nombres de archivo y patrones de contenido
   asociados a exfiltracion de credenciales.
4. **Instalacion reproducible** -- existe ``package-lock.json`` (npm es el
   gestor oficial) y ``.npmrc`` declara ``ignore-scripts=true``.

Las comprobaciones 1-3 recorren el arbol ``node_modules`` REAL y son agnosticas
al gestor: funcionan igual con pnpm o npm. Solo la comprobacion 4 es especifica
del lockfile.

Uso:
    python -m scripts.verify_supply_chain
    python -m scripts.verify_supply_chain --json
    python -m scripts.verify_supply_chain --allow-install-scripts esbuild
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from app.common.errors import ConfigurationError
from app.config import PROJECT_ROOT

DENYLIST_PATH = PROJECT_ROOT / "config" / "supply_chain_denylist.yaml"
FRONTEND = PROJECT_ROOT / "frontend"
NODE_MODULES = FRONTEND / "node_modules"

#: Extensiones que se inspeccionan en busca de patrones de exfiltracion.
SCANNED_SUFFIXES = frozenset({".js", ".cjs", ".mjs", ".ts"})
#: Un archivo mayor que esto casi seguro es un bundle legitimo minificado.
MAX_SCAN_BYTES = 2 * 1024 * 1024


@dataclass
class Finding:
    severity: str
    kind: str
    detail: str
    location: str = ""


@dataclass
class Report:
    checked_packages: int = 0
    findings: list[Finding] = field(default_factory=list)
    checks: dict[str, str] = field(default_factory=dict)

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "critical"]

    @property
    def ok(self) -> bool:
        return not self.blocking

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "checked_packages": self.checked_packages,
            "checks": self.checks,
            "blocking": [asdict(f) for f in self.blocking],
            "warnings": [asdict(f) for f in self.findings if f.severity != "critical"],
        }


def load_denylist(path: Path | None = None) -> dict:
    target = path or DENYLIST_PATH
    if not target.exists():
        raise ConfigurationError(f"No existe la lista de bloqueo: {target}")
    try:
        return yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        raise ConfigurationError(
            f"La lista de bloqueo es invalida: {target.name}", detail=str(exc)
        ) from exc


def iter_installed_packages(root: Path):  # noqa: ANN201
    """Genera ``(nombre, version, ruta)`` de cada paquete instalado.

    Se recorre ``node_modules`` completo, incluidos los anidados: un paquete
    comprometido puede aparecer como dependencia transitiva profunda y no en el
    primer nivel.
    """
    if not root.is_dir():
        return
    for manifest in root.rglob("package.json"):
        # Solo manifiestos que estan directamente bajo un directorio de paquete.
        if manifest.parent.name in ("dist", "src", "lib", "test", "tests"):
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError):
            continue
        name = data.get("name")
        if not isinstance(name, str) or not name:
            continue
        yield name, str(data.get("version", "")), manifest.parent, data


def _version_matches(version: str, allowed) -> bool:  # noqa: ANN001
    if allowed == "*" or allowed is None:
        return True
    if isinstance(allowed, str):
        return version == allowed
    return version in set(allowed)


def check_denylist(report: Report, denylist: dict, packages: list[tuple]) -> None:
    """Comprueba que ningun paquete comprometido este presente."""
    bloqueados = 0
    for incident in denylist.get("incidents", []):
        incident_id = incident.get("id", "sin-id")
        for entry in incident.get("packages", []):
            nombre = entry.get("name")
            versiones = entry.get("versions", "*")
            for pkg_name, pkg_version, pkg_path, _ in packages:
                if pkg_name == nombre and _version_matches(pkg_version, versiones):
                    bloqueados += 1
                    report.findings.append(
                        Finding(
                            severity="critical",
                            kind="paquete_en_lista_de_bloqueo",
                            detail=f"{pkg_name}@{pkg_version} ({incident_id})",
                            location=str(pkg_path),
                        )
                    )
    report.checks["lista_de_bloqueo"] = "OK" if bloqueados == 0 else f"FAIL ({bloqueados})"


def check_install_scripts(report: Report, packages: list[tuple], allowed: set[str]) -> None:
    """Detecta paquetes con scripts de ciclo de vida de instalacion."""
    encontrados = []
    for pkg_name, pkg_version, pkg_path, data in packages:
        scripts = data.get("scripts") or {}
        if not isinstance(scripts, dict):
            continue
        presentes = [s for s in ("preinstall", "install", "postinstall") if scripts.get(s)]
        if not presentes:
            continue
        if pkg_name in allowed:
            report.findings.append(
                Finding(
                    severity="info",
                    kind="script_de_instalacion_permitido",
                    detail=f"{pkg_name}@{pkg_version}: {', '.join(presentes)}",
                    location=str(pkg_path),
                )
            )
            continue
        encontrados.append(pkg_name)
        report.findings.append(
            Finding(
                # No es critico por si mismo: es critico que se EJECUTE. Con
                # ignore-scripts=true no se ejecuta. Se reporta como aviso para
                # que quede a la vista en cada instalacion.
                severity="warning",
                kind="script_de_instalacion",
                detail=f"{pkg_name}@{pkg_version}: {', '.join(presentes)}",
                location=str(pkg_path),
            )
        )
    report.checks["scripts_de_instalacion"] = (
        "OK (ninguno)" if not encontrados else f"REVISAR ({len(encontrados)})"
    )


def check_indicators(report: Report, denylist: dict, root: Path) -> None:
    """Busca indicadores de compromiso en el arbol instalado."""
    indicadores = denylist.get("indicators", {})
    patrones_nombre = indicadores.get("filenames", [])
    patrones_contenido = [re.compile(p) for p in indicadores.get("content_patterns", [])]

    coincidencias = 0

    if root.is_dir():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(fnmatch.fnmatch(path.name.lower(), p.lower()) for p in patrones_nombre):
                coincidencias += 1
                report.findings.append(
                    Finding(
                        severity="critical",
                        kind="ioc_nombre_de_archivo",
                        detail=path.name,
                        location=str(path),
                    )
                )
                continue
            if path.suffix.lower() not in SCANNED_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_SCAN_BYTES:
                    continue
                contenido = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for patron in patrones_contenido:
                if patron.search(contenido):
                    coincidencias += 1
                    report.findings.append(
                        Finding(
                            severity="critical",
                            kind="ioc_contenido",
                            detail=patron.pattern,
                            location=str(path),
                        )
                    )
                    break

    report.checks["indicadores_de_compromiso"] = (
        "OK" if coincidencias == 0 else f"FAIL ({coincidencias})"
    )


def check_reproducible_install(report: Report) -> None:
    """Verifica lockfile y que los scripts esten bloqueados por configuracion.

    El gestor oficial es npm y el flujo desplegado usa ``npm ci``. Por ello,
    cualquier otro lockfile es irrelevante para este control.
    """
    npm_lock = FRONTEND / "package-lock.json"
    if npm_lock.exists():
        report.checks["lockfile"] = "OK (package-lock.json)"
    else:
        report.checks["lockfile"] = "FAIL"
        report.findings.append(
            Finding(
                severity="critical",
                kind="sin_lockfile",
                detail="falta frontend/package-lock.json: npm ci no es reproducible",
            )
        )

    npmrc = FRONTEND / ".npmrc"
    contenido = npmrc.read_text(encoding="utf-8") if npmrc.exists() else ""
    if re.search(r"^\s*ignore-scripts\s*=\s*true", contenido, re.MULTILINE):
        report.checks["ignore_scripts"] = "OK"
    else:
        report.checks["ignore_scripts"] = "FAIL"
        report.findings.append(
            Finding(
                severity="critical",
                kind="scripts_de_instalacion_habilitados",
                detail="frontend/.npmrc no declara ignore-scripts=true",
            )
        )


#: npm viene con Node; fijamos su version exacta para hacer auditable el toolchain.
_NPM_EXACT = re.compile(r"^npm@\d+\.\d+\.\d+$")


def package_manager_pin(frontend: Path | None = None) -> tuple[str, bool]:
    """Devuelve ``(valor_packageManager, es_npm_con_version_exacta)``.

    Reutilizable por el empaquetado de release, que exige el hash de forma
    bloqueante.
    """
    manifest = (frontend or FRONTEND) / "package.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "", False
    pm = data.get("packageManager")
    if not isinstance(pm, str) or not pm:
        return "", False
    return pm, bool(_NPM_EXACT.match(pm))


def check_package_manager_pin(report: Report) -> None:
    """npm debe declararse con version exacta en package.json."""
    pm, valido = package_manager_pin()
    if not pm:
        report.checks["gestor_fijado"] = "REVISAR (sin packageManager)"
        report.findings.append(
            Finding(
                severity="warning",
                kind="gestor_no_fijado",
                detail="frontend/package.json no declara packageManager (fije npm@x.y.z)",
            )
        )
    elif not valido:
        report.checks["gestor_fijado"] = "REVISAR (se esperaba npm@x.y.z)"
        report.findings.append(
            Finding(
                severity="warning",
                kind="gestor_no_canonico",
                detail=f"packageManager={pm}; se esperaba npm con version exacta",
            )
        )
    else:
        report.checks["gestor_fijado"] = f"OK ({pm})"


def run(*, allowed_script_packages: set[str] | None = None) -> Report:
    report = Report()
    denylist = load_denylist()

    packages = list(iter_installed_packages(NODE_MODULES))
    report.checked_packages = len(packages)

    if not packages:
        report.checks["arbol_instalado"] = (
            "AUSENTE (ejecute 'npm ci --ignore-scripts' en frontend/)"
        )
    else:
        report.checks["arbol_instalado"] = f"OK ({len(packages)} manifiestos)"

    check_denylist(report, denylist, packages)
    check_install_scripts(report, packages, allowed_script_packages or set())
    check_indicators(report, denylist, NODE_MODULES)
    check_reproducible_install(report)
    check_package_manager_pin(report)
    return report


def render(report: Report) -> str:
    lineas = ["", "=== CADENA DE SUMINISTRO (npm) ===", ""]
    for nombre, estado in report.checks.items():
        marca = "[ OK ]" if estado.startswith("OK") else "[FAIL]"
        if estado.startswith(("AUSENTE", "REVISAR")):
            marca = "[WARN]"
        lineas.append(f"{marca} {nombre:28s} {estado}")

    avisos_scripts = [
        f for f in report.findings
        if f.severity == "warning" and f.kind == "script_de_instalacion"
    ]
    if avisos_scripts:
        lineas.append("")
        lineas.append(f"Paquetes con script de instalacion ({len(avisos_scripts)}):")
        for aviso in avisos_scripts[:20]:
            lineas.append(f"    {aviso.detail}")
        lineas.append("    (no se ejecutan: ignore-scripts=true)")

    otros_avisos = [
        f for f in report.findings
        if f.severity == "warning" and f.kind != "script_de_instalacion"
    ]
    if otros_avisos:
        lineas.append("")
        lineas.append(f"Avisos ({len(otros_avisos)}):")
        for aviso in otros_avisos[:20]:
            lineas.append(f"    [{aviso.kind}] {aviso.detail}")

    if report.blocking:
        lineas.append("")
        lineas.append("HALLAZGOS BLOQUEANTES:")
        for hallazgo in report.blocking:
            lineas.append(f"    [{hallazgo.kind}] {hallazgo.detail}")
            if hallazgo.location:
                lineas.append(f"        {hallazgo.location}")

    lineas.append("")
    lineas.append("RESULTADO: " + ("CADENA DE SUMINISTRO OK" if report.ok else "CADENA DE SUMINISTRO COMPROMETIDA"))
    lineas.append("")
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verificacion de cadena de suministro de Matrix RH")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--allow-install-scripts",
        nargs="*",
        default=[],
        help="paquetes cuyo script de instalacion se acepta explicitamente",
    )
    args = parser.parse_args(argv)

    report = run(allowed_script_packages=set(args.allow_install_scripts))
    payload = report.as_dict()

    if args.output:
        destino = Path(args.output)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else render(report))
    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
