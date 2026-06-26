# Contribuindo

Obrigado por querer contribuir com o projeto.

## Ambiente de desenvolvimento

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

Instale também o FFmpeg e garanta que `ffmpeg` e `ffprobe` estejam disponíveis no PATH.

## Qualidade

Antes de abrir um pull request, execute:

```powershell
ruff check .
mypy .
pytest
```

## Commits

Use Conventional Commits:

- `feat: nova funcionalidade`
- `fix: correção de bug`
- `docs: documentação`
- `test: testes`
- `refactor: reorganização sem mudança de comportamento`
- `chore: tarefas de manutenção`

## Pull requests

Inclua:

- descrição objetiva da mudança;
- passos para testar;
- impacto esperado para usuários;
- capturas de tela quando a interface for alterada.
