<!-- Creado por Aldo Garcia. -->

# scripts/

Scripts de shell para entornos no-Windows.

`matrixrh.sh` es el equivalente de los `.bat` para entornos no-Windows y delega
en los mismos módulos Python (no duplica lógica). Subcomandos: `install`,
`start`, `stop`, `diagnose` y `validate`. Al igual que el instalador de Windows,
`install` usa `uv sync --frozen`,
`corepack pnpm install --frozen-lockfile --ignore-scripts` y verifica la cadena
de suministro antes de compilar el frontend.

`validate` no tiene lanzador `.bat` en la raíz (en Windows se ejecuta con
`powershell -File windows\Validate-MatrixRH.ps1`); aquí se conserva como
subcomando por comodidad en Linux/macOS.

```bash
./scripts/matrixrh.sh install
```
```bash
./scripts/matrixrh.sh start
```

En Windows use los `.bat` de la raíz.
