# Validação

Executada em 2026-10-15, Linux x86_64.

## Refatoração 0.2

- 13 testes automatizados passaram: entrada explícita, credenciais obrigatórias para ambos os motores, proteção de arquivos existentes, falha de verificação sem publicação, isolamento Godot, identidade/orientação, resolução npm interna/externa e adaptações Expo.
- Verificação estática Python passou (`ruff check --select F` e `compileall`).
- Pacote Python construído como wheel e instalado; `doctor` de ambos os motores executado de outra pasta.
- Expo mínimo SDK 54: npm, prebuild, pods, JS/Hermes, módulos Swift, 81 fontes C/ObjC/C++, linkagem, assinatura e verificação passaram num cache novo fora do clone e do workspace anterior.
- Godot mínimo 4.5.1: importação, exportação PCK, compilação do suporte, linkagem, assinatura e verificação passaram pelo pacote instalado. Bibliotecas genéricas da toolchain; nenhum jogo anterior como dependência.
- Novo verificador validou o IPA Godot e recusou uma cópia com o PCK adulterado.
- Grafos e comandos de compilação Expo novos foram conferidos sem referências ao workspace anterior.
- Código revisado para excluir caminhos pessoais, certificados, senhas, sessões Apple, SDKs e IPAs da publicação.

## Testes no aparelho

Em 2026-10-15, os IPAs **Expo-Portable-01** e **Godot-Portable-01**, produzidos após a refatoração, foram instalados no iPhone. O usuário confirmou a abertura e o funcionamento dos dois exemplos: “os dois abriram e funcionaram 100%”.

Essa confirmação valida o uso dos exemplos mínimos no aparelho testado. Não representa teste exaustivo de outros projetos, dependências nativas ou recursos como compras e anúncios.

## Não verificado

Bootstrap integral em máquina limpa; outros compiladores/SDKs; Linux arm64; versões antigas de iOS; compras, anúncios e distribuição na App Store. A verificação CMS local não consulta revogação ou confiança na Apple.
