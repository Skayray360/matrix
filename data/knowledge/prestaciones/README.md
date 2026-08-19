<!-- Creado por Aldo Garcia. -->

# prestaciones/ (compatibilidad)

Corpus heredado de prestaciones, vacaciones, aguinaldo y fondo de ahorro. La
reconciliación conserva la categoría efectiva `prestaciones` para no romper una
instalación existente.

- Entradas: `.docx`, `.md`, `.pdf`, `.txt`, `.xlsx` o `.csv` oficiales.
- Salida: chunks corporativos con categoría `prestaciones` y filtro RBAC.
- Dependencias: política `prestaciones` y roles vigentes en el backend.

No agregue aquí documentación nueva si ya existe una clasificación aprobada en
`general/` o `especializadas/<dominio>/`. Migre sólo mediante un cambio
controlado de política, pruebas positivas y negativas y reindexación; mover un
archivo cambia su categoría efectiva. Este `README.md` se excluye de la ingesta.
