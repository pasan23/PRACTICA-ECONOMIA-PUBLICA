"""Reproducción offline desde la raíz o cualquier directorio: python reproducir.py --pdf --package."""

from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent


def archivos_entrega():
    names = ["README.md", "requirements.txt", "reproducir.py", "informe_completo.pdf"]
    files = [ROOT / name for name in names]
    for folder, pattern in [
        ("data", "*.json"),
        ("notebooks", "*.ipynb"),
        ("src", "*.py"),
        ("latex", "*.tex"),
    ]:
        files.extend(sorted((ROOT / folder).glob(pattern)))
    return files


def paquete_entrega():
    dest = ROOT / "entrega.zip"
    files = archivos_entrega()
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, Path("economia_publica_covid") / path.relative_to(ROOT))
    return dest


def run(args, cwd=ROOT):
    subprocess.run([str(x) for x in args], cwd=cwd, check=True)


def manifest():
    # Huellas para comprobar qué archivos y versiones se utilizaron.
    files = []
    for path in archivos_entrega():
        if path.exists():
            files.append(path)
    packages = [
        "numpy",
        "pandas",
        "scipy",
        "statsmodels",
        "matplotlib",
        "seaborn",
        "nbformat",
        "nbclient",
        "ipykernel",
    ]
    versions = {}
    for package in packages:
        versions[package] = importlib.metadata.version(package)
    hashes = {}
    for path in files:
        relative_path = str(path.relative_to(ROOT))
        hashes[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    data = {"python": sys.version.split()[0], "versions": versions, "sha256": hashes}
    (ROOT / ".resultados/verificacion.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--package", action="store_true")
    args = parser.parse_args()
    if args.package and not args.pdf:
        parser.error("--package requiere --pdf")
    os.environ.setdefault("SOURCE_DATE_EPOCH", "1790208000")
    os.environ.setdefault(
        "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "covid-mpl")
    )
    # Preparar los datos, generar las salidas y comprobar las reglas del análisis.
    run([sys.executable, "-m", "src.prepare_data"])
    run([sys.executable, "-m", "src.build_outputs"])
    run([sys.executable, "-m", "unittest", "discover", "-s", "src", "-v"])
    import nbformat
    from nbclient import NotebookClient

    # Kernel explícito de este intérprete, sin depender del Python global.
    from jupyter_client.kernelspec import KernelSpecManager
    from jupyter_client.manager import KernelManager

    with tempfile.TemporaryDirectory(prefix="covid-kernel-") as temp:
        spec = Path(temp) / "covid"
        spec.mkdir()
        (spec / "kernel.json").write_text(
            json.dumps(
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "ipykernel_launcher",
                        "-f",
                        "{connection_file}",
                    ],
                    "display_name": "COVID reproducible",
                    "language": "python",
                }
            )
        )
        manager = KernelSpecManager(kernel_dirs=[temp])
        for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
            nb = nbformat.read(path, as_version=4)
            for cell in nb.cells:
                cell.metadata.pop("execution", None)
            km = KernelManager(kernel_name="covid", kernel_spec_manager=manager)
            NotebookClient(
                nb,
                km=km,
                timeout=180,
                record_timing=False,
                resources={"metadata": {"path": str(ROOT)}},
            ).execute()
            nbformat.validate(nb)
            nbformat.write(nb, path)
            print("Ejecutado:", path.name, flush=True)
    if args.pdf:
        tectonic = os.environ.get("TECTONIC") or shutil.which("tectonic")
        latexmk = shutil.which("latexmk")
        if not tectonic and not latexmk:
            raise SystemExit(
                "Falta Tectonic o latexmk. Instalarlo o definir TECTONIC=/ruta/tectonic."
            )
        build = ROOT / ".resultados/pdf"
        for source in (ROOT / "latex").glob("*.tex"):
            shutil.copy2(source, build / source.name)
        if tectonic:
            command = [tectonic, "--keep-logs", "informe_completo.tex"]
        else:
            command = [
                latexmk,
                "-pdf",
                "-interaction=nonstopmode",
                "informe_completo.tex",
            ]
        run(command, build)
        shutil.copy2(build / "informe_completo.pdf", ROOT / "informe_completo.pdf")
    manifest()
    if args.package:
        print("Entrega completa:", paquete_entrega())
    print("Reproducción completa.", flush=True)


if __name__ == "__main__":
    main()
