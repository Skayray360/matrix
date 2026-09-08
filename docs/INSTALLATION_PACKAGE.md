<!-- Estrategia del paquete unificado de Matrix RH. -->

# Paquete de instalacion unificado

## Recomendacion

Un paquete unificado si tiene sentido para Matrix RH, siempre que sea un
bootstrapper y no intente empotrar todas las dependencias externas. MySQL,
Ollama y sus modelos tienen ciclos de vida, tamaños y licencias independientes.

La unidad de entrega recomendada es `MatrixRH-<version>.zip`. Incluye codigo,
frontend compilado, locks, migraciones, scripts, documentacion y el instalador
`INSTALAR_MATRIX_RH.bat`. Al extraerlo, el operador usa un unico punto de
entrada; el instalador valida los prerrequisitos y genera secretos locales.

## Generacion

```powershell
.\MATRIX-DEV.ps1 check
.\MATRIX-DEV.ps1 package
```

El empaquetador existente rechaza secretos, archivos runtime y entregas sin
`pnpm-lock.yaml` o sin hash criptografico del gestor. El ZIP se crea junto a la
carpeta del repositorio.

## Evolucion recomendada

Para distribucion corporativa puede envolverse el ZIP en WiX Toolset o MSIX,
firmar scripts/binarios y publicar SHA-256 del artefacto. Ese instalador deberia:

1. comprobar Python 3.12, Ollama, MySQL y espacio disponible;
2. ofrecer instalar prerrequisitos solo desde origen corporativo aprobado;
3. descargar modelos con consentimiento y progreso visible;
4. ejecutar instalacion, preflight y smoke test;
5. registrar version, ruta y procedimiento de desinstalacion;
6. nunca incluir `.env`, contraseñas, certificados ni datos reales.

No se recomienda convertir la aplicacion en un ejecutable Python monolitico:
drivers, modelos y servicios seguirian siendo externos y se perderia claridad
operacional sin eliminar los prerrequisitos relevantes.
