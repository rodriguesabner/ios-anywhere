# Toolchain externa

O CLI está separado dos aplicativos, mas o bootstrap de uma máquina limpa **ainda é manual**. Não há download automático de SDKs Apple nem distribuição dos binários neste repositório. Use SDKs obtidos por meios permitidos e confira as licenças de cada ferramenta.

## Layout esperado

O campo `toolchain` do config aponta para uma pasta com:

```text
toolchain/
  swift/usr/bin/{swiftc,clang,clang++}
  darwin-tools/bin/ld64.lld
  sdks/{iPhoneOS18.5.sdk,iPhoneOS26.4.sdk,iPhoneOS26.5.sdk}/
  darwin-resource/
    clang -> ../swift/usr/lib/clang/21
    shims -> ../swift/usr/lib/swift/shims
    iphoneos/{Cxx.swiftmodule,CxxStdlib.swiftmodule,libcxxshim.h,libcxxshim.modulemap,libcxxstdlibshim.h}
  ruby/usr/bin/ruby3.2
  ruby/usr/lib/...
  gems/{bin/pod,gems/...}
  apple-macros/{OpenAppleMacrosServer,plugins/...}
  host-macros/ExpoModulesMacros-tool
  os_version_check.o
  cxx-runtime/{compat-markers.o,Cxx.o,modules/Cxx.swiftmodule/...}
  signing/{package.json,package-lock.json,node_modules/zsign-wasm/...}
  godot/{godot,libgodot.a,libMoltenVK.a}
```

Os campos `llvm_ar` e `installer` aceitam um executável no PATH ou caminho absoluto. `installer_lib`, opcional, define `LD_LIBRARY_PATH` só para libimobiledevice. Nenhuma credencial deve ser guardada na toolchain ou no repositório.

## Componentes usados no ambiente validado

| Componente | Origem/versão | Uso |
| --- | --- | --- |
| Swift Linux | Swift 6.4 RELEASE | Swift, Clang e shims |
| Linker Mach-O | [darwin-tools-linux-llvm v1.1.0](https://github.com/xtool-org/darwin-tools-linux-llvm/releases/tag/v1.1.0) | `ld64.lld` |
| Macros Apple no Linux | [OpenAppleMacros v1.3.0](https://github.com/xtool-org/OpenAppleMacros/releases/tag/v1.3.0) | servidor de plugins Swift |
| SDK iOS | 18.5, 26.4 e 26.5 | Godot; compilação Expo; linkagem Expo, respectivamente |
| Ruby/CocoaPods | Ruby 3.2, CocoaPods 1.17.0 | resolução de pods e exportação do projeto |
| Macros Expo | plugin Linux compilado para o Expo instalado | `host-macros/ExpoModulesMacros-tool` |
| Assinador | npm `zsign-wasm@0.0.4` | assinatura local |
| Godot | editor Linux 4.5.1 + bibliotecas iOS release arm64 4.5.1 | PCK e engine |
| LLVM ar | LLVM 18 no ambiente testado | arquivos estáticos |

Os arquivos Darwin `Cxx`/`CxxStdlib` precisam corresponder ao compilador. O toolchain Swift para Linux sozinho não inclui todos os overlays Apple necessários. O diretório de macros contém o servidor Linux e os pontos de entrada de plugins esperados pelos interfaces do SDK. A macro Expo deve ser compilada para o host, não copiada de um executável macOS do npm. Esses itens são requisitos reais, não são instalados por `doctor`.

O conjunto de SDKs usado foi obtido do mirror `xybp888/iOS-SDKs`, revisão `ad607cb07fe4ad1c9b91cf970bd228c2a9253207`. Nos SDKs 26.5 e 27 desse mirror, `System/Library/PrivateFrameworks/UIKitCore.framework/UIKitCore.tbd` foi desativado (renomeado para `.tbd.mirror-backup`) porque o stub privado incompleto sobrepunha o público. Isso é específico desse conjunto; não aplique a outro SDK sem avaliar. O backend Expo usa SDK 26.4 para compilação C/Swift e 26.5 para linkagem. Os stubs 26.4 desse mirror omitem símbolos Swift de frameworks públicos, incluindo StoreKit. O SDK 27 não é mais selecionado pelo pipeline.

Para preparar apenas o assinador, em uma pasta externa:

```sh
npm install --prefix "$TOOLCHAIN/signing" --save-exact zsign-wasm@0.0.4
```

O pacote Python inclui os scripts do CLI; os scripts RubyGem devem usar `#!/usr/bin/env ruby` para evitar caminhos de uma máquina anterior. O backend configura Ruby, GEM_HOME, GEM_PATH e os wrappers de compilação por processo.

## Objetos de runtime

Com compilador e SDKs disponíveis:

```sh
python3 ios_linux/scripts/prepare-runtime.py --toolchain "$TOOLCHAIN"
```

Para projetos Swift/C++, acrescente os fontes de [Swift 6.2 Cxx](https://github.com/swiftlang/swift/tree/swift-6.2-RELEASE/stdlib/public/Cxx):

```sh
python3 ios_linux/scripts/prepare-runtime.py \
  --toolchain "$TOOLCHAIN" \
  --cxx-sources /caminho/swift-6.2/stdlib/public/Cxx
```

O overlay é isolado em `cxx-runtime/modules`; o overlay padrão do compilador é preservado. O alvo do overlay é iOS 16.4. Reexecute o comando acima ao atualizar de uma instalação cujo overlay foi compilado para iOS 27. Isso não substitui testes de execução em aparelhos antigos. A combinação evita referências a `Swift.Iterable` que o aparelho usado no teste não fornecia. Arquivos binários de módulos não são universais entre compiladores: recompile ao trocar Swift.

## Godot

Obtenha o editor Linux e o template iOS oficial da mesma versão. Coloque o editor em `godot/godot`, a biblioteca release **arm64 de dispositivo** em `godot/libgodot.a` e a biblioteca MoltenVK correspondente em `godot/libMoltenVK.a`. Não use slices de simulador. O CLI cria seu próprio suporte mínimo; não exige exportar um jogo anterior nem copiar os assets desse jogo.

## Portabilidade e limpeza

A pasta de ferramentas pode ser movida se a configuração e os links internos forem ajustados. Os caminhos do clone e dos apps não são usados como fallback. `doctor` detecta arquivos necessários ausentes, mas não substitui um build real para avaliar compatibilidade entre versões.

O cache de um projeto pode ser apagado com todos os builds parados; o próximo build refaz dependências, grafos e módulos. A toolchain é durável: não é cache de projeto. Nunca apague sua pasta para limpar builds.
