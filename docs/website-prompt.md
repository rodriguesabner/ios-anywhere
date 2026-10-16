# Prompt: site do ios-anywhere

Copie o texto abaixo para a ferramenta ou agente que vai criar o site.

---

Crie um site de apresentação bonito, rápido e responsivo para **ios-anywhere**, um CLI experimental que compila, assina e instala apps iOS localmente no Linux, com backends Expo e Godot. Repositório: https://github.com/rodriguesabner/ios-anywhere.

Antes de escrever o conteúdo, leia README.md, docs/toolchain.md, docs/validation.md e pyproject.toml do repositório. Use esses arquivos como fonte de verdade. Se o repositório privado não estiver acessível, peça esses arquivos; não invente capacidades.

## Direção visual

Quero uma ferramenta técnica com identidade forte, inspirada na clareza de https://github.com/morluto/rea e https://github.com/boykopovar/AnyPS5, sem copiar marcas, textos ou imagens. Tema grafite quase preto, texto marfim, acento verde-lima discreto e detalhes em azul frio. Tipografia sans-serif legível, monospace apenas para comandos e rótulos técnicos. Espaçamento generoso, bordas finas, composição editorial e um terminal demonstrativo como elemento central. Evite gradientes roxos, excesso de cartões, emojis decorativos e promessas genéricas de IA.

O hero deve dizer “Do seu projeto ao iPhone.” e explicar abaixo “Builds locais de Expo e Godot no Linux.” Mostre o selo “Experimental” perto da proposta, sem escondê-lo no rodapé. O nome anywhere é a marca; não prometa suporte universal a sistemas operacionais.

## Estrutura e conteúdo

1. Cabeçalho compacto com marca, links para Como funciona, Compatibilidade, Começar e GitHub.
2. Hero com CTAs “Começar” (âncora da instalação) e “Ver no GitHub”. Inclua diagrama claro: Projeto → Compilar → Assinar → IPA → iPhone.
3. Terminal com abas Expo e Godot, comandos reais copiados do README e botão Copiar. Identifique o terminal como exemplo de comando, não um build acontecendo no navegador. Use caminhos e identidades fictícios como /caminho/meu-app e com.example.meujogo. Mostre os parâmetros globais antes do subcomando.
4. Explicação curta de cada etapa, destacando projeto explícito, toolchain externa e cache separado.
5. Tabela honesta de compatibilidade: Expo SDK 54 e Godot 4.5.1 nos exemplos testados; Linux x86_64 validado; widgets/extensões fora do fluxo genérico; Godot C# e GDExtensions não suportados; dependências nativas exigem validação. Atualize apenas se a documentação comprovar outro estado.
6. Instalação com clone, venv e pip install local. Explique que instalar o pacote não instala SDKs, compiladores ou credenciais. Link para docs/toolchain.md. Comando principal ios-anywhere; ios-linux permanece alias.
7. FAQ: precisa de Mac para executar o fluxo preparado? Usa EAS Build? Precisa de certificado? Funciona com qualquer app? Pode enviar à App Store? Responda com os limites documentados. Certificado e perfil válidos continuam necessários. Não prometa aprovação da Apple; catálogos de assets pré-compilados ainda são necessários.
8. Rodapé com links reais para repositório, toolchain, arquitetura e validação. Não invente Discord, licença, preços, depoimentos, métricas, estrelas ou clientes.

## Implementação e publicação

Faça um site estático em site/ com HTML, CSS e JavaScript mínimo, sem backend, banco, cadastro ou upload de arquivos. O site apresenta o CLI; não compila ou assina aplicativos. Nenhuma dependência de SDKs locais ou arquivos pessoais.

Prepare GitHub Pages com GitHub Actions oficial para upload e deploy do artefato site/, com permissões mínimas, ambiente github-pages, workflow_dispatch e execução em push na branch padrão apenas quando site/ ou o workflow mudar. Descubra a branch real antes de configurar. Todos os caminhos devem funcionar no subdiretório /ios-anywhere/, sem quebrar CSS, links e imagens. Use recursos locais sempre que possível.

Mantenha o repositório privado. Antes de habilitar ou executar a publicação, confira a disponibilidade de Pages para a conta/plano e apresente a visibilidade efetiva do site para aprovação. Nunca torne o repositório público para contornar uma limitação. O material do site deve ser revisado separadamente do código privado. Não publique certificados, chaves, UDIDs, provisioning profiles, IPAs, dados de apps, logs ou toolchains.

## Qualidade e entrega

Garanta navegação por teclado, foco visível, contraste adequado, HTML semântico, layout sem rolagem horizontal a partir de 360 px, respeito a prefers-reduced-motion e terminal sem armadilhas de acessibilidade. Copiar deve exibir confirmação acessível e lidar com falha da área de transferência. Inclua título, descrição e favicon próprios; não invente URL de produção ativa.

Valide em tamanhos de celular e desktop, confira todos os links locais e teste as abas e o botão Copiar. Entregue arquivos, instruções de preview e deploy, capturas reais do resultado e uma lista curta do que não foi validado. Prepare tudo para revisão antes de publicar. Não implemente funcionalidades extras além desta landing page.
