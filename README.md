# Video Translator

Aplicação desktop em Python para gerar legendas em português do Brasil para episódios de séries em turco. O app usa `faster-whisper` com o modelo `large-v3`, detecta GPU NVIDIA com CUDA quando disponível, divide vídeos grandes em partes de áudio, transcreve em turco, traduz para pt-BR e exporta um `.srt` sincronizado na mesma pasta do vídeo.

Exemplo:

```text
Daha17_Ep01.mp4
Daha17_Ep01.pt-BR.srt
```

## Funcionalidades

- Interface moderna com CustomTkinter e tema escuro.
- Interface web local com upload, fila, progresso e download da legenda.
- Seleção de vídeos pelo explorador de arquivos.
- Arrastar e soltar vídeos quando `tkinterdnd2` estiver disponível.
- Processamento de múltiplos episódios em fila.
- Transcrição em turco com Whisper `large-v3`.
- Tradução automática para português do Brasil.
- Geração de `.srt` sincronizado.
- Barra de progresso por etapa: modelo, transcrição, tradução, legenda e exportação.
- Estimativa de tempo restante.
- Cancelamento do processamento.
- Histórico dos últimos vídeos.
- Pré-visualização da legenda gerada.
- Botão para abrir a legenda ao finalizar.
- Opção de incorporar a legenda ao vídeo com FFmpeg.
- No site local, botão para gerar e baixar o vídeo com legenda embutida.
- Logs completos em `logs/app.log`.
- Configuração persistente em `config.json`.
- Projeto preparado para GitHub, CI, testes, lint e build por Release.

## Estrutura

```text
.
├── assets/
├── docs/
├── gui/
├── logs/
├── models/
├── output/
├── src/
├── tests/
├── config.json
├── main.py
├── requirements.txt
├── requirements-dev.txt
└── video-translator.spec
```

## Pré-requisitos

- Windows 10 ou 11.
- Python 3.10 ou superior.
- FFmpeg instalado e disponível no PATH.
- Internet no primeiro uso para baixar o modelo Whisper e para a tradução via `deep-translator`.
- Opcional: GPU NVIDIA com CUDA configurado.

## Instalação do FFmpeg

Uma opção simples no Windows é usar Winget:

```powershell
winget install Gyan.FFmpeg
```

Depois feche e abra o terminal e valide:

```powershell
ffmpeg -version
ffprobe -version
```

## Ambiente virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

## Instalação das dependências

Para uso normal:

```powershell
pip install -r requirements.txt
```

Para desenvolvimento:

```powershell
pip install -r requirements-dev.txt
```

## Executar a aplicação desktop

```powershell
python main.py
```

Na interface:

1. Clique em `Selecionar vídeos`.
2. Escolha um ou mais arquivos `.mp4`, `.mkv` ou `.avi`.
3. Clique em `Iniciar`.
4. Aguarde a geração da legenda.
5. Clique em `Abrir legenda` ao finalizar.

## Executar o site local

```powershell
python -m src.web_app
```

Depois acesse:

```text
http://127.0.0.1:8000
```

O site oferece duas formas de adicionar episódios:

- upload pelo navegador, salvando o vídeo temporariamente em `output/uploads`;
- caminho local, preservando a geração da legenda na mesma pasta do arquivo original.

Quando o processamento terminar, use `Baixar SRT` para salvar a legenda gerada ou
`Gerar vídeo legendado` para criar uma cópia do episódio com a legenda embutida.
Depois que o vídeo terminar de ser criado, use `Baixar vídeo`.

## Configuração

O arquivo `config.json` controla idioma, modelo, uso de GPU, tamanho das legendas, pasta padrão e interface.

Campos principais:

- `language.source`: idioma original, definido como `tr`.
- `language.target`: idioma final, definido como `pt-BR`.
- `whisper.model`: modelo Whisper, por padrão `large-v3`.
- `hardware.use_gpu`: tenta usar CUDA quando disponível.
- `hardware.cpu_threads`: `0` usa todos os núcleos detectados.
- `subtitles.max_chars_per_line`: máximo de caracteres por linha.
- `subtitles.max_lines`: máximo de linhas por legenda.
- `processing.chunk_minutes`: duração de cada parte extraída do vídeo.
- `interface.recent_videos`: histórico salvo automaticamente.

## Qualidade da legenda

O pipeline aplica:

- transcrição forçada em turco;
- correções simples de reconhecimento;
- pontuação e capitalização;
- quebra em no máximo duas linhas;
- duração mínima e máxima por legenda;
- ajuste de tempo de leitura;
- pequenos intervalos entre legendas para melhorar leitura;
- tradução para português natural via `deep-translator`.

Nomes próprios tendem a ser preservados pelo tradutor, mas traduções automáticas podem exigir revisão humana em casos de nomes raros, apelidos e expressões muito regionais.

## Gerar executável Windows

Com o ambiente de desenvolvimento ativo:

```powershell
pyinstaller video-translator.spec --clean --noconfirm
```

Saída:

```text
dist/VideoTranslator/VideoTranslator.exe
```

Também existe um workflow em `.github/workflows/release-build.yml` que gera um ZIP do executável quando uma Release é publicada no GitHub.

## Testes e qualidade

```powershell
ruff check .
mypy .
pytest
```

O workflow `.github/workflows/ci.yml` executa lint, type check e testes automaticamente a cada push ou pull request.

## Git e GitHub

Comandos finais para publicar:

```powershell
git init
git add .
git commit -m "feat: versão inicial do gerador de legendas"
git branch -M main
git remote add origin <URL_DO_REPOSITORIO>
git push -u origin main
```

## Solução de problemas

### FFmpeg não encontrado

Instale o FFmpeg e confirme que `ffmpeg` e `ffprobe` funcionam no terminal.

### O modelo Whisper demora para carregar

O `large-v3` é grande e pode demorar no primeiro uso. Em CPU, o processamento pode levar bastante tempo para episódios longos.

### Sem GPU NVIDIA

O app usa CPU automaticamente. Para acelerar, configure `hardware.cpu_threads` em `config.json` ou deixe `0` para usar todos os núcleos.

### Erro durante tradução

`deep-translator` depende de serviço externo. Verifique a internet e consulte `logs/app.log`.

### Legenda atrasada ou adiantada

O app ajusta tempos automaticamente, mas materiais com áudio ruim, múltiplas vozes ou música alta podem exigir revisão manual em um editor de legendas.

### Executável abre mas não processa

Confirme se FFmpeg está instalado no Windows onde o executável está rodando. O executável não embute FFmpeg.

## FAQ

### Posso usar outro modelo Whisper?

Sim. Altere `whisper.model` em `config.json`. Exemplos: `medium`, `large-v2`, `large-v3`.

### A tradução é perfeita?

Não. Ela é automática e pensada para gerar uma boa primeira versão em pt-BR. Revisão humana ainda é recomendada para publicação.

### Posso processar vários episódios?

Sim. Selecione múltiplos vídeos; eles entram em fila e são processados um por vez.

### Onde ficam os logs?

Em `logs/app.log`.

### Onde a legenda é salva?

Na mesma pasta do vídeo, usando o mesmo nome base e o sufixo `.pt-BR.srt`.

## Licença

MIT. Consulte `LICENSE`.
