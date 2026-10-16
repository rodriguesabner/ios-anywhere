<div align="center">

# ios-anywhere

### Do seu projeto ao iPhone. Build local no Linux.

**Expo · Godot · Compilação · Assinatura · Instalação**

![Status: experimental](https://img.shields.io/badge/status-experimental-f0b429)
![Host: Linux x86_64](https://img.shields.io/badge/host-Linux_x86__64-20252b)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)

[Começar](#instalação) · [Expo](#expo) · [Godot](#godot) · [Compatibilidade](#compatibilidade) · [Documentação](#documentação)

</div>

---

CLI experimental para compilar, assinar e instalar apps iOS **localmente no Linux**, com backends **Expo** e **Godot**. Não usa Mac nem EAS Build. Expo ainda usa a Expo CLI local para prebuild e bundle JavaScript.

O código não depende de nenhum app anterior. Cada build recebe um projeto, credenciais próprias e um destino. Compiladores, SDKs e caches ficam fora do repositório.

```text
Projeto Expo / Godot → compilação local → assinatura → IPA → iPhone
```

## Compatibilidade

| Caminho | Estado atual |
| --- | --- |
| Expo | Exemplos SDK 54 compilados e testados em iPhone; dependências nativas podem exigir adaptações. |
| Godot | GDScript com engine 4.5.1; exemplos compilados e testados em iPhone. |
| Assinatura | Certificado e provisioning profile válidos fornecidos pelo usuário. |
| Widgets e extensões | Ainda fora do fluxo genérico deste CLI. |
| App Store | Experimental; upload não equivale a processamento ou aprovação. Assets compilados ainda são necessários. |
| Sistemas hospedeiros | Linux x86_64 validado. Windows e macOS não foram validados. |

Veja a evidência e o escopo dos testes em [Validação](docs/validation.md).

## Instalação

Python 3.11+, Node/npm, OpenSSL e Pillow são necessários. Instale o CLI a partir deste repositório:

```sh
git clone https://github.com/rodriguesabner/ios-anywhere.git
cd ios-anywhere
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/ios-anywhere --version
```

Prepare a toolchain conforme [docs/toolchain.md](docs/toolchain.md), copie `config.example.json` para `~/.config/ios-linux/config.json` e ajuste os caminhos. **Instalar o pacote Python não instala compiladores, SDKs ou credenciais Apple.**

```sh
ios-anywhere doctor
ios-anywhere --engine godot doctor
```

Use `--config /caminho/config.json` para outra configuração. O comando instalado pela venv fica em `.venv/bin/ios-anywhere`; adicione essa pasta ao PATH ou ative a venv.

## Expo

```sh
ios-anywhere --engine expo \
  --project /caminho/meu-app \
  --credentials /caminho/privado/credentials.json \
  build --output /caminho/MeuApp-01.ipa
```

O projeto precisa de `package.json`, `package-lock.json` e configuração Expo com `ios.bundleIdentifier`. O CLI cria uma cópia, roda `npm ci`, prebuild iOS e CocoaPods, gera os grafos do próprio app, compila os módulos nativos, gera Hermes e assina o IPA. O código fonte original não é editado. Pacotes npm e scripts do projeto são executados: use fontes em que confia.

## Godot

```sh
ios-anywhere --engine godot \
  --project /caminho/meu-jogo \
  --bundle-id com.example.meujogo \
  --credentials /caminho/privado/credentials.json \
  build --output /caminho/MeuJogo-01.ipa
```

A fonte precisa conter `project.godot`. O backend exporta um PCK novo, linka o engine iOS arm64 instalado na toolchain e aplica identidade, nome, orientação e ícone PNG do projeto. Use editor e engine da mesma versão; o ambiente validado usa Godot 4.5.1.

## Assinatura, instalação e verificação

Use o formato de `credentials.example.json`. Caminhos de certificado e perfil são relativos ao arquivo de credenciais ou absolutos. O perfil deve corresponder à identidade do app e incluir o aparelho. Certificado, senha e perfil são fornecidos por você; o CLI não entra na conta Apple nem cria perfis automaticamente.

```sh
ios-anywhere verify /caminho/MeuApp-01.ipa
ios-anywhere install /caminho/MeuApp-01.ipa --udid SEU_UDID
```

`verify` verifica hashes de código, recursos e assinatura CMS, além da correspondência com o perfil. Não consulta confiança/revogação na Apple, não valida compatibilidade de App Store e não prova funcionamento no aparelho. `IOS_LINUX_UDID` pode restringir a verificação ao aparelho pretendido.

`build` só publica o IPA depois da assinatura e verificação. Destinos existentes são recusados. A instalação é separada. `bundle` prepara e gera apenas recursos, sem assinatura. As opções globais (`--project`, `--credentials`, `--engine`, `--config`) vêm antes do comando.

## Nome novo, configuração preservada

O comando principal agora é `ios-anywhere`. `ios-linux` continua como alias. Os caminhos `~/.config/ios-linux`, `~/.local/share/ios-linux`, `~/.cache/ios-linux` e as variáveis `IOS_LINUX_*` foram mantidos para reutilizar instalações existentes. O módulo Python interno continua `ios_linux`.

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
- Swift/C++ usa um overlay de compatibilidade separado, que deve ser recompilado após atualizar o CLI. O backend Expo configura mínimo 16.4; versões antigas do iOS não foram testadas. Godot configura mínimo 14.0, também sem validação em aparelhos antigos.
- Godot: GDScript, engine padrão sem plugins externos; C# e GDExtensions são recusados. Versão/build são 1.0/1 neste backend. Recursos de privacidade específicos do jogo precisam de revisão antes de distribuição.
- App Store: catálogos de assets ainda precisam ser pré-compilados. O empacotamento preserva `Assets.car` e ícones presentes em `build/app-resources`; gerar apenas PNGs não atende à exigência de catálogo da Apple.
- A toolchain é instalada separadamente. SDKs Apple, bibliotecas de terceiros e credenciais não são publicados no repositório.

## Desenvolvimento

```sh
python3 -m unittest discover -s tests -v
```

Veja [docs/validation.md](docs/validation.md) para os testes reais e [docs/architecture.md](docs/architecture.md) para os limites entre código, ferramentas e builds.

## Perguntas frequentes

**Preciso de Mac para executar este fluxo?** Não no ambiente Linux preparado. A toolchain e os SDKs são pré-requisitos externos; o pacote Python não os instala.

**Preciso do EAS Build?** Não. O backend Expo usa ferramentas locais do ecossistema Expo. Enviar o IPA a uma loja é uma etapa separada.

**Funciona com qualquer app?** Não. Os backends cobrem os caminhos descritos acima. Projetos com recursos nativos diferentes precisam de validação própria.

**Dispensa certificado Apple?** Não. O CLI assina com suas credenciais e respeita as restrições do provisioning profile.

## Documentação

- [Preparar a toolchain](docs/toolchain.md)
- [Arquitetura e isolamento dos projetos](docs/architecture.md)
- [Validação e testes em aparelho](docs/validation.md)
- [Dependências e avisos de terceiros](THIRD_PARTY.md)
- [Prompt para criar o site](docs/website-prompt.md)

## Disclaimer

Veja [DISCLAIMER.md](DISCLAIMER.md) para orientações de uso responsável, aplicáveis a todas as versões, plataformas e canais de distribuição do ios-anywhere. Cada cópia mantém suas licenças aplicáveis.

O projeto destina-se ao desenvolvimento, à pesquisa, à educação, à interoperabilidade e à preservação de software que você possui ou está autorizado a usar, modificar e distribuir. A assinatura exige credenciais válidas; o CLI não concede direitos de distribuição nem aprovação na App Store.

## Contributing

Contribuições são bem-vindas! [Abra uma issue](https://github.com/rodriguesabner/ios-anywhere/issues) para relatar um bug ou sugerir uma melhoria, ou [envie um pull request](https://github.com/rodriguesabner/ios-anywhere/pulls) com alterações no código ou na documentação. O acesso depende das permissões do repositório privado.

Veja [CONTRIBUTING.md](CONTRIBUTING.md) para preparar o ambiente e executar as verificações, [Validação](docs/validation.md) para o escopo dos testes e [Arquitetura](docs/architecture.md) para a estrutura do projeto.

## License

O código próprio do ios-anywhere é licenciado sob a [MIT](LICENSE). Material de terceiros mantém suas licenças e avisos de copyright; veja [Componentes de terceiros](THIRD_PARTY.md).

**Você deve obter e estar autorizado a usar as ferramentas e os SDKs externos**, incluindo os SDKs Apple e as dependências da toolchain, conforme seus respectivos termos. O ios-anywhere não concede licença de ferramenta, chave ou direito de ativação. Cópias não autorizadas, chaves roubadas, compartilhamento indevido de credenciais e contorno de restrições de licença não são autorizados pelo projeto. Essa orientação não modifica a MIT nem as licenças de terceiros.
