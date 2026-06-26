# Build Windows

## Pré-requisitos

- Python 3.10 ou superior.
- FFmpeg instalado e disponível no PATH.
- Ambiente virtual ativo.
- Dependências instaladas com `pip install -r requirements-dev.txt`.

## Gerar executável

```powershell
pyinstaller video-translator.spec --clean --noconfirm
```

O executável será gerado em:

```text
dist/VideoTranslator/VideoTranslator.exe
```

## Observações

O modelo Whisper pode ser baixado no primeiro uso. Para distribuir em computadores sem internet,
execute a aplicação uma vez no ambiente de destino ou configure cache local do faster-whisper.
