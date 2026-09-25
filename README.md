# La composición del gasto público antes y después de la pandemia

**Pablo Sánchez González · Universidad Complutense de Madrid · Economía Pública**

Estudio de los 27 países de la UE, 2015–2024. Compara la composición del gasto entre 2017–2019 y 2022–2024, sin atribuir causalmente las diferencias a la pandemia.

## Contenido de la entrega

- **informe_completo.pdf**: artículo con portada, resultados y anexo nacional.
- **notebooks/**: cuaderno principal y cuestiones metodológicas (ceros institucionales y comparación por periodos).
- **data/**: única instantánea original de Eurostat.
- **src/**: preparación de datos, análisis, figuras y controles de consistencia.
- **latex/**: fuente del artículo y estilo.
- **reproducir.py** y **requirements.txt**: reproducción y dependencias.

Esta es la carpeta completa que se entrega. `entrega.zip` contiene únicamente estos 13 archivos; excluye entornos, respaldos y resultados intermedios.

## Reproducción

Con Python 3.11, desde esta carpeta:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python reproducir.py
```

Esto calcula los resultados, ejecuta los controles y actualiza los dos cuadernos de arriba abajo. En Windows, sustituir `.venv/bin/python` por `.venv\Scripts\python.exe`.

Para regenerar también el PDF y el ZIP, instalar Tectonic o LaTeX con `latexmk`, y ejecutar:

```sh
.venv/bin/python reproducir.py --pdf --package
```

Si Tectonic no está en PATH, puede indicarse con `TECTONIC=/ruta/tectonic`. La primera compilación puede necesitar conexión para obtener paquetes tipográficos. Los cálculos utilizan exclusivamente la instantánea incluida y no requieren descargar datos.

Los archivos intermedios se crean automáticamente en `.resultados/`. No son entradas necesarias ni forman parte de la entrega. Las versiones de ejecución y huellas de los archivos se registran allí. Para editar el documento, modificar `latex/` y repetir la reproducción; las cifras y figuras se generan a partir del análisis.

## Datos y alcance

Fuente: [Eurostat, gov_10a_exp](https://doi.org/10.2908/GOV_10A_EXP), gasto total y todas las funciones COFOG. Instantánea actualizada el 16-09-2026; se desconoce la fecha exacta de descarga original. SHA-256: `8f8b6bcc2bf7d52d7181b163293347d15ecd7a7d7b1aad9b361dd7cb622022b2`.

La documentación institucional y las reglas de tratamiento están en el cuaderno metodológico y en las fuentes de los PDF. Se conservan exclusivamente referencias a los datos y a su documentación técnica.

Las participaciones se calculan sobre la suma no consolidada de los cuatro subsectores, con igual peso por país. Describen la composición contable del gasto, no directamente la autonomía fiscal. Los contrastes son exploratorios y están sujetos a dependencia entre países, revisiones estadísticas y elección de periodos.
