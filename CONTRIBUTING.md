# Contribuindo com ios-anywhere

Relate bugs ou proponha melhorias nas [issues](https://github.com/rodriguesabner/ios-anywhere/issues). Para alterações no código ou na documentação, envie um [pull request](https://github.com/rodriguesabner/ios-anywhere/pulls). O repositório é privado: esses recursos exigem acesso.

## Preparação

Use Python 3.11 ou mais recente:

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/ios-anywhere --help
```

Os testes unitários não exigem certificados, aparelho ou SDKs Apple. Builds reais precisam da [toolchain externa](docs/toolchain.md). Leia a [arquitetura](docs/architecture.md) antes de alterar os backends.

## Verificação

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q ios_linux tests
git diff --check
```

Inclua um teste pequeno para lógica nova ou correção de regressão. Documente mudanças de configuração, comandos e compatibilidade. Preserve o alias `ios-linux`, os caminhos existentes e as variáveis `IOS_LINUX_*`, salvo migração explícita.

## Relatos e pull requests

Informe versão do CLI, distribuição/arquitetura Linux, engine e versão, comando usado, resultado esperado e erro observado. Remova segredos e dados pessoais dos logs. Use um exemplo mínimo que você possa compartilhar, sem anexar SDKs, IPAs ou projetos privados de terceiros.

Descreva o problema, a mudança e os testes executados. Distinga teste unitário, build concluído, instalação, execução no aparelho e processamento na App Store. Não apresente uma etapa como prova das demais. Veja [Validação](docs/validation.md).

Preserve avisos de copyright e licenças de material reutilizado; atualize [THIRD_PARTY.md](THIRD_PARTY.md) quando necessário. Contribuições próprias são destinadas à licença MIT do projeto; material de terceiros mantém seus termos. Contribua apenas com material que você está autorizado a compartilhar.
