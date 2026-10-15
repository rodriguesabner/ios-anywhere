# Arquitetura

`cli.py` valida os argumentos, verifica a configuração e impede builds concorrentes no mesmo cache. `config.py` conhece apenas a toolchain e o cache; nenhum projeto é armazenado como padrão.

`expo.py` resolve dependências e grafos na cópia isolada do projeto. Os scripts recebem `IOS_LINUX_PROJECT`, `IOS_LINUX_BUILD` e `IOS_LINUX_TOOLCHAIN` explicitamente. Wrapper de clang/Ruby e exportador Xcode são parte do pacote; SDKs e executáveis são recursos externos.

`godot.py` copia o projeto, exporta PCK e linka bibliotecas genéricas do engine. Não usa um projeto exportado anterior como template. `templates/` contém apenas o suporte nativo mínimo e o manifesto padrão de privacidade do Godot, com a atribuição de origem preservada.

`signing.py` recebe a mesma configuração de credenciais nos dois backends. Assina uma pasta `.app`, gera um IPA temporário, verifica e publica com criação sem sobrescrita. Não armazena senhas no repositório, em argumentos de processo ou em relatórios.

A instalação usa libimobiledevice configurado localmente. A verificação de um IPA não exige toolchain nem login; usa Python e OpenSSL. Relatórios não afirmam validação no aparelho automaticamente.

## Migração da versão de laboratório

A versão 0.2 remove projetos implícitos, perfis fixos, provisionamento com conta pessoal e `--workspace`. Configure `--config`, passe `--project` sempre e forneça `--credentials` também para Godot. `package` isolado foi removido para evitar assinatura acidental de produtos antigos; use `build`. O comando `verify` permite inspecionar IPAs existentes.

Nada da fonte original deve ser usado como diretório de saída de compilação. Configurações de projeto que apontem para fora da cópia ou usem fases Xcode personalizadas podem exigir adaptação. O CLI executa projetos confiáveis; não constitui sandbox para código de terceiros.
