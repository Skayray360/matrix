<!-- Creado por Aldo Garcia. -->

# Gobierno de documentación oficial

Matrix RH separa el corpus corporativo permanente de los adjuntos privados de
chat. Una carga no cambia de ámbito por el texto de una pregunta ni por una
decisión del modelo.

## Estructura oficial

```text
data/knowledge/
├── general/
│   └── <tema>/<archivo>
└── especializadas/
    └── <dominio>/<archivo>
```

- `general/` contiene políticas y procedimientos destinados a todas las
  identidades con `HCM_EMP_BASICO_MX`. Las subcarpetas organizan temas, pero no
  amplían permisos.
- `especializadas/` contiene repositorios por dominio. Cada dominio necesita
  una política explícita y los grupos `HCM_ADM_*` o `HCM_COORD_*` que
  correspondan.
- Nómina se divide siempre en dos dominios independientes: General y
  Confidencial. No se coloca un archivo confidencial en una carpeta compartida
  para resolverlo después con instrucciones al modelo.

La semántica técnica exacta de cada ruta y su categoría efectiva se describe en
[`../data/knowledge/README.md`](../data/knowledge/README.md). Esa tabla es el
contrato operativo: debe actualizarse junto con cualquier cambio en el
descubridor de archivos o en `config/authorization/categories.yaml`.

## Qué puede publicarse

Formatos admitidos: `.docx`, `.md`, `.pdf`, `.txt`, `.xlsx` y `.csv`. Los
`README.md` del repositorio no se indexan. Un PDF escaneado sin capa de texto no
se somete a OCR implícito: queda sin evidencia utilizable y con un aviso.

La reconciliación ignora archivos ocultos, extensiones no soportadas, documentos
en la raíz de `data/knowledge/`, archivos directos en `especializadas/` y dominios
con slug inválido o reservado. Un aviso de clasificación no debe resolverse
moviendo el archivo a una carpeta más amplia: corrija su dominio y política.

Antes de publicar:

1. confirme que el documento es oficial, vigente y tiene propietario funcional;
2. clasifique `general` o el dominio especializado correcto;
3. separe físicamente Nómina General de Nómina Confidencial;
4. retire secretos, credenciales y datos personales no necesarios;
5. use un nombre estable y versionado por el proceso documental;
6. ejecute la reconciliación y revise estado, advertencias y número de chunks;
7. pruebe un usuario autorizado y otro no autorizado.

## Publicar en un dominio nuevo (de principio a fin)

Si tus archivos van a `general/`, **no hay configuración adicional**: es accesible
con el perfil base `HCM_EMP_BASICO_MX`. Salta al paso 4.

Para un **dominio especializado nuevo** (una carpeta que aún no existe en la
política), la carpeta recién creada queda **deny-by-default**: se indexa, pero
ningún rol la recibe —y por tanto el modelo nunca la ve— hasta que se declara y
se concede. Recorrido completo:

1. **Crea la carpeta** del dominio en
   `data/knowledge/especializadas/<dominio>/` (minúsculas, dígitos, `_` o `-`; no
   uses `general` ni `especializadas` como nombre de dominio).

2. **Declara la categoría** en `config/authorization/categories.yaml`:

   ```yaml
   - name: <dominio>
     description: <para qué es este dominio>
     sensitivity: confidential        # internal | confidential | restricted
     wildcard_eligible: true          # false = concesión nominal obligatoria
     allowed_groups:
       - HCM_ADM_<DOMINIO>_MX
       - HCM_COORD_<DOMINIO>_MX
     source_owner: rh_<dominio>
   ```

   Aparecer aquí **no concede acceso por sí solo**: define la taxonomía, la
   sensibilidad y los grupos que podrán tenerla.

3. **Concede el acceso a un rol** y sincroniza. Si el grupo/rol es nuevo, declara
   también su mapeo en `config/authorization/entra-role-mapping.yaml`. Después
   materializa roles, categorías y permisos en la base (idempotente); primero en
   seco y luego aplicando:

   ```bat
   set "PYTHONPATH=%CD%\backend"
   .venv\Scripts\python.exe -m scripts.load_entra_mapping --dry-run
   ```
   ```bat
   set "PYTHONPATH=%CD%\backend"
   .venv\Scripts\python.exe -m scripts.load_entra_mapping --prune
   ```

   > **Para probar con la cuenta local `Matrix` (sin Entra ID):** si el dominio es
   > `wildcard_eligible: true`, el wildcard del administrador de prueba ya lo
   > cubre tras este paso. Un dominio `restricted` / `wildcard_eligible: false`
   > exige concesión nominal explícita.

4. **Coloca los archivos** (`.docx`, `.md`, `.pdf`, `.txt`, `.xlsx`, `.csv`) en la
   carpeta y **reconcilia**:

   ```bat
   set "PYTHONPATH=%CD%\backend"
   .venv\Scripts\python.exe -m scripts.bootstrap ingest
   ```

5. **Verifica** estado, advertencias y número de chunks:

   ```bat
   set "PYTHONPATH=%CD%\backend"
   .venv\Scripts\python.exe -m scripts.bootstrap status
   ```

6. **Prueba** con un usuario autorizado (debe recibir la evidencia con sus
   fuentes) y con uno no autorizado (no debe confirmarse que el material existe).

> **Síntoma más común:** «indexé mis archivos y responde que no tiene
> información». Casi siempre es el paso 2 o 3 pendiente: la categoría existe en
> disco, pero no está declarada en `categories.yaml` o no está concedida al rol
> con el que iniciaste sesión. La ingesta por sí sola nunca abre acceso.

## Ingesta y actualización

La reconciliación calcula SHA-256. Un archivo sin cambios no se vuelve a
indexar; una versión nueva reemplaza primero los vectores anteriores y después
publica los nuevos. El scheduler repite la reconciliación según
`RAG_REINDEX_INTERVAL_HOURS` (24 horas por defecto).

Desde la raíz del proyecto, en `cmd.exe`:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.bootstrap ingest
```

Para reindexar aunque el SHA no haya cambiado:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.bootstrap ingest --force
```

La ruta administrativa `POST /api/v1/admin/knowledge/documents` requiere
`knowledge.admin` **y** que la categoría esté en el alcance efectivo del rol.
Guarda en `general/<archivo>` o
`especializadas/<dominio>/<archivo>` según la categoría. No convierte un adjunto
de conversación en conocimiento corporativo de forma automática.

## Adjuntos privados y resumen

Un archivo adjunto al chat vive en la colección privada y sólo se recupera con
la pareja `user_id + conversation_id`. Para resumirlo:

1. adjunte el archivo y espere el estado `indexed`;
2. pida de forma explícita un resumen, por ejemplo: «Resume el archivo adjunto»;
3. Matrix RH recupera los fragmentos del adjunto dentro de esa conversación;
4. la respuesta se genera sólo con esos fragmentos, se verifican sus citas y se
   muestran sus fuentes;
5. al borrar la conversación se eliminan sus vectores privados.

No confundir este resumen de contenido con el resumen interno de una
conversación larga: este último sólo conserva continuidad de diálogo y no puede
actuar como fuente factual.

## Límite documental (*document-grounded*)

Para políticas, procesos, cifras, plazos, requisitos o contenido de un archivo,
los modelos responden únicamente con evidencia autorizada. Si la recuperación
no aporta evidencia suficiente, Matrix RH lo declara; no completa huecos con
conocimiento general. La capacidad completa de los modelos se usa para
comprender, organizar, comparar y redactar, nunca para saltar ACL ni inventar
fuentes.
