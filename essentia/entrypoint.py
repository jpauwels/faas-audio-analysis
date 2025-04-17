import subprocess
import pathlib
from typing import Annotated
from fastapi import Body, FastAPI, Path, Response, status


app = FastAPI()


@app.post("/")
def process_default(
    file: Annotated[bytes, Body(media_type='audio/*')],
    response: Response,
):
    return process(file, '', response)


@app.post("/{file_name}")
def process(
    file: Annotated[bytes, Body(media_type='audio/*')],
    file_name: Annotated[str, Path()],
    response: Response,
):
    try:
        proc = subprocess.run([pathlib.Path(__file__).parent / 'run-essentia.sh', file_name], input=file, capture_output=True, check=True)
    except subprocess.CalledProcessError as err:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return dict(error=dict(code=err.returncode, message=err.stderr.decode()))
    return Response(proc.stdout.decode(), media_type='application/json')
