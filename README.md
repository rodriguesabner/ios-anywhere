# ios-linux

CLI experimental para compilar, assinar e instalar apps iOS **localmente no Linux**, com backends **Expo** e **Godot**. Não usa Mac nem EAS Build. Expo ainda usa a Expo CLI local para prebuild e bundle JavaScript.

O código não depende de nenhum app anterior. Cada build recebe um projeto, credenciais próprias e um destino. Compiladores, SDKs e caches ficam fora do repositório.

## Instalação

Python 3.11+, Node/npm, OpenSSL e Pillow são necessários. Instale o CLI a partir deste repositório:

```sh
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/ios-linux --version
```

Prepare a toolchain conforme [docs/toolchain.md](docs/toolchain.md), copie `config.example.json` para `~/.config/ios-linux/config.json` e ajuste os caminhos. **Instalar o pacote Python não instala compiladores, SDKs ou credenciais Apple.**

```sh
ios-linux doctor
ios-linux --engine godot doctor
```

Use `--config /caminho/config.json` para outra configuração. O comando instalado pela venv fica em `.venv/bin/ios-linux`; adicione essa pasta ao PATH ou ative a venv.

## Expo

```sh
ios-linux --engine expo \
  --project /caminho/meu-app \
  --credentials /caminho/privado/credentials.json \
  build --output /caminho/MeuApp-01.ipa
```

O projeto precisa de `package.json`, `package-lock.json` e configuração Expo com `ios.bundleIdentifier`. O CLI cria uma cópia, roda `npm ci`, prebuild iOS e CocoaPods, gera os grafos do próprio app, compila os módulos nativos, gera Hermes e assina o IPA. O código fonte original não é editado. Pacotes npm e scripts do projeto são executados: use fontes em que confia.

## Godot

```sh
ios-linux --engine godot \
  --project /caminho/meu-jogo \
  --bundle-id com.example.meujogo \
  --credentials /caminho/privado/credentials.json \
  build --output /caminho/MeuJogo-01.ipa
```

A fonte precisa conter `project.godot`. O backend exporta um PCK novo, linka o engine iOS arm64 instalado na toolchain e aplica identidade, nome, orientação e ícone PNG do projeto. Use editor e engine da mesma versão; o ambiente validado usa Godot 4.5.1.

## Assinatura, instalação e verificação

Use o formato de `credentials.example.json`. Caminhos de certificado e perfil são relativos ao arquivo de credenciais ou absolutos. O perfil deve corresponder à identidade do app e incluir o aparelho. Certificado, senha e perfil são fornecidos por você; o CLI não entra na conta Apple nem cria perfis automaticamente.

```sh
ios-linux verify /caminho/MeuApp-01.ipa
ios-linux install /caminho/MeuApp-01.ipa --udid SEU_UDID
```

`verify` verifica hashes de código, recursos e assinatura CMS, além da correspondência com o perfil. Não consulta confiança/revogação na Apple, não valida compatibilidade de App Store e não prova funcionamento no aparelho. `IOS_LINUX_UDID` pode restringir a verificação ao aparelho pretendido.

`build` só publica o IPA depois da assinatura e verificação. Destinos existentes são recusados. A instalação é separada. `bundle` prepara e gera apenas recursos, sem assinatura. As opções globais (`--project`, `--credentials`, `--engine`, `--config`) vêm antes do comando.

## Organização

- `ios_linux/`: CLI, configuração e backends.
- `ios_linux/scripts/`: compilação, exportação de grafos e assinatura compartilhadas.
- `examples/`: apps mínimos independentes Expo e Godot; ajuste a identidade Expo antes de assinar.
- `tests/`: testes sem certificados, aparelho ou SDKs Apple.
- Toolchain externa: `~/.local/share/ios-linux/toolchain`.
- Cache descartável: `~/.cache/ios-linux`; contém cópias de fontes, recursos, produtos e logs. Não compartilhe esse cache: apps e configurações podem conter dados privados.
- Configuração local: `~/.config/ios-linux/config.json`.

Nenhum projeto é selecionado implicitamente. Não há dependência do diretório de execução nem do local do clone. O cache inclui caminhos absolutos gerados pelo CocoaPods; após movê-lo, refaça o build. Não mova/apague toolchain ou cache durante uma compilação.

## Limites

- Experimental, validado em Linux x86_64. Não é um substituto universal do Xcode.
- Expo: SDK 54 validado, app principal Swift com AppDelegate padrão. Extensões/widgets, fases nativas especiais, storyboards personalizados e AppDelegates próprios exigem suporte adicional. O fluxo antigo específico de widgets não faz parte desta distribuição.
- Swift/C++ usa um overlay de compatibilidade separado; esses projetos exigem iOS 27 nesta implementação. Apps sem esse overlay têm mínimo 16.4 configurado; versões antigas do iOS não foram testadas. Godot configura mínimo 14.0, também sem validação em aparelhos antigos.
- Godot: GDScript, engine padrão sem plugins externos; C# e GDExtensions são recusados. Versão/build são 1.0/1 neste backend. Recursos de privacidade específicos do jogo precisam de revisão antes de distribuição.
- A toolchain é instalada separadamente. SDKs Apple, bibliotecas de terceiros e credenciais não são publicados no repositório.

## Desenvolvimento

```sh
python3 -m unittest discover -s tests -v
```

Veja [docs/validation.md](docs/validation.md) para os testes reais e [docs/architecture.md](docs/architecture.md) para os limites entre código, ferramentas e builds.
