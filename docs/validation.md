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

Antes da refatoração, o app Expo mínimo e projetos reais Expo/Godot tiveram abertura/uso confirmados pelo usuário no iPhone. Os IPAs produzidos **após** a refatoração passaram na compilação e verificação local, mas ainda precisam de teste manual no aparelho. Não extrapole a confirmação anterior para dependências ou funções não testadas.

## Não verificado

Bootstrap integral em máquina limpa; outros compiladores/SDKs; Linux arm64; versões antigas de iOS; compras, anúncios e distribuição na App Store. A verificação CMS local não consulta revogação ou confiança na Apple.
