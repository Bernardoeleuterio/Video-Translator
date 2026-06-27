# Interface web local

Execute:

```powershell
python -m src.web_app
```

Acesse:

```text
http://127.0.0.1:8000
```

## Modos de entrada

### Upload

O navegador envia o vídeo para `output/uploads`. A legenda será gerada nessa pasta e poderá
ser baixada pela página.

### Caminho local

Cole o caminho completo do vídeo no campo `Caminho local`. Nesse modo, o servidor processa
o arquivo diretamente e salva o `.pt-BR.srt` na mesma pasta do vídeo.

## Endpoints

- `POST /api/jobs/upload`: cria um job por upload.
- `POST /api/jobs/path`: cria um job usando caminho local.
- `GET /api/jobs`: lista jobs.
- `GET /api/jobs/{job_id}`: consulta um job.
- `POST /api/jobs/{job_id}/cancel`: cancela um job.
- `GET /api/jobs/{job_id}/subtitle`: baixa a legenda.
- `GET /api/logs`: baixa os logs.
