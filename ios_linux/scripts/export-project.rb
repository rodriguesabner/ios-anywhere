require 'xcodeproj'
require 'json'
project = Xcodeproj::Project.open(ARGV.fetch(0))
keys = %w[SWIFT_OBJC_INTEROP_MODE SWIFT_ACTIVE_COMPILATION_CONDITIONS MARKETING_VERSION CURRENT_PROJECT_VERSION PRODUCT_MODULE_NAME PRODUCT_NAME GCC_PREPROCESSOR_DEFINITIONS HEADER_SEARCH_PATHS FRAMEWORK_SEARCH_PATHS LIBRARY_SEARCH_PATHS OTHER_CFLAGS OTHER_CPLUSPLUSFLAGS OTHER_SWIFT_FLAGS OTHER_LDFLAGS CLANG_CXX_LANGUAGE_STANDARD CLANG_ENABLE_OBJC_ARC GCC_PREFIX_HEADER SWIFT_VERSION SWIFT_OBJC_BRIDGING_HEADER MODULEMAP_FILE PODS_TARGET_SRCROOT IPHONEOS_DEPLOYMENT_TARGET INFOPLIST_FILE PRODUCT_BUNDLE_IDENTIFIER EXECUTABLE_NAME ASSETCATALOG_COMPILER_APPICON_NAME APPLICATION_EXTENSION_API_ONLY]
ENV['PODS_CONFIGURATION_BUILD_DIR'] = File.join(ENV.fetch('IOS_LINUX_BUILD'), 'products')
ENV['CONFIGURATION_BUILD_DIR'] = ENV['PODS_CONFIGURATION_BUILD_DIR']
ENV['PODS_ROOT'] = (project.path.basename.to_s == 'Pods.xcodeproj' ? project.project_dir : project.project_dir + 'Pods').to_s
ENV['SDKROOT'] = File.join(ENV.fetch('IOS_LINUX_TOOLCHAIN'), 'sdks/iPhoneOS26.4.sdk')
ENV['PLATFORM_NAME'] = 'iphoneos'
ENV['EFFECTIVE_PLATFORM_NAME'] = '-iphoneos'
rows = project.targets.select { |t| t.respond_to?(:source_build_phase) }.map do |target|
 config = target.build_configurations.find { |c| c.name == 'Release' }
 {
  name: target.name,
  settings: keys.to_h { |k| [k,config.resolve_build_setting(k,target)] },
  sources: target.source_build_phase.files.map { |f| {path: f.file_ref.real_path.to_s, flags: f.settings} },
  headers: target.headers_build_phase.files.map { |f| {path: f.file_ref.real_path.to_s, flags: f.settings} },
  resources: target.resources_build_phase.files.map { |f| f.file_ref.real_path.to_s },
  dependencies: target.dependencies.map { |d| d.target&.name }.compact,
  scripts: target.shell_script_build_phases.map { |s| {name:s.name,script:s.shell_script} }
 }
end
abort 'No targets found' if rows.empty?
puts JSON.pretty_generate(rows)
