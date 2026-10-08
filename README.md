# MetaDataCleaner

Herramienta offline para normalizar y re-encodear imágenes en Windows.

## Características

- Procesamiento local: las imágenes no se envían a servidores.
- Normalización mediante re-encodeado.
- Compatible con JPG/JPEG, PNG y WebP.
- Conserva los archivos originales.
- Genera una copia con el sufijo `_CLEAN`.
- Aplicación portable para Windows.

## Uso

1. Abre **MetaDataCleaner.exe**.
2. Agrega una o más imágenes.
3. Ejecuta la normalización.
4. Las copias procesadas se guardan junto a los originales con el sufijo `_CLEAN`.

## Compilación

El proyecto se puede compilar localmente con Python y PyInstaller. También incluye un workflow de GitHub Actions que genera automáticamente `MetaDataCleaner.exe` para Windows en cada push a `main` y mediante ejecución manual.

## Nota

La normalización está orientada a privacidad, compatibilidad y estandarización de archivos. No garantiza ningún resultado frente a sistemas externos de detección o clasificación.

## Licencia

MIT License.
