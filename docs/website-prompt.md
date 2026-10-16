# Prompt: ios-anywhere website

Copy the following prompt into the tool or agent that will create the website.

---

Create a polished, fast, responsive presentation website for **ios-anywhere**, an experimental CLI that compiles, signs, and installs iOS apps locally on Linux, with Expo and Godot backends. Repository: https://github.com/rodriguesabner/ios-anywhere.

Before writing content, read README.md, docs/toolchain.md, docs/validation.md, llm.txt, and pyproject.toml in the repository. Treat these as the source of truth. If the repository is inaccessible, request those files; do not invent capabilities. Write all website content in English.

## Visual direction

Create a developer tool identity inspired by the clarity of https://github.com/morluto/rea and https://github.com/boykopovar/AnyPS5, without copying brands, text, or images. Use near-black graphite, ivory text, restrained lime accents, and cool blue details. Use a readable sans-serif font, with monospace reserved for commands and technical labels. Favor generous spacing, thin borders, editorial composition, and a demo terminal as the central visual. Avoid purple gradients, excessive cards, decorative emoji, and generic AI claims.

The hero should say “From your project to your iPhone.” with “Local Expo and Godot builds on Linux.” underneath. Display an “Experimental” label near the value proposition, not hidden in the footer. Anywhere is the brand; do not promise universal operating system support.

## Structure and content

1. Compact header with the brand and links to How it works, Compatibility, Get started, and GitHub.
2. Hero with “Get started” linking to installation and “View on GitHub”. Include a clear diagram: Project → Compile → Sign → IPA → iPhone.
3. Terminal with Expo and Godot tabs, real commands from the README, and a Copy button. Label it as a command example, not a live browser build. Use fictional paths and identities such as /path/to/my-app and com.example.mygame. Place global options before the subcommand.
4. Brief explanation of each stage, highlighting explicit projects, an external toolchain, and separate caches.
5. Honest compatibility table: Expo SDK 54 and Godot 4.5.1 in tested examples; Linux x86_64 validated; widgets/extensions outside the generic workflow; Godot C# and GDExtensions unsupported; native dependencies require validation. Update these claims only when the documentation proves another status.
6. Installation with clone, venv, and local pip install. Explain that the package does not install SDKs, compilers, or credentials. Link to docs/toolchain.md. Use ios-anywhere as the primary command.
7. FAQ covering Mac requirements, EAS Build, certificates, arbitrary apps, and App Store submission. Use documented limits. Valid certificates and profiles remain required. Do not promise Apple approval; precompiled asset catalogs are still necessary. Show the external EAS Submit command from the README only as a separate upload step.
8. Footer linking to the real repository, toolchain, architecture, validation, disclaimer, contributing guide, and license. Do not invent a Discord server, prices, testimonials, metrics, stars, or customers.

## Implementation and publishing

Build a static website in site/ using HTML, CSS, and minimal JavaScript. No backend, database, registration, or file uploads. The website presents the CLI; it does not compile or sign applications. Do not depend on local SDKs or personal files.

Prepare GitHub Pages using official GitHub Actions for artifact upload and deployment of site/, minimum permissions, the github-pages environment, workflow_dispatch, and pushes to the actual default branch only when site/ or its workflow changes. Discover the branch before configuring it. Paths must work under /ios-anywhere/ without breaking CSS, links, or images. Prefer local assets.

The repository is public. Do not change its visibility. Before enabling or executing website publication, check Pages availability for the account/plan and present the site's actual visibility for approval. Review website material before publication. Never publish certificates, keys, UDIDs, provisioning profiles, IPAs, application data, logs, or toolchains.

## Quality and delivery

Ensure keyboard navigation, visible focus, sufficient contrast, semantic HTML, no horizontal page overflow from 360 px upward, reduced-motion support, and an accessible terminal. Copy must announce success accessibly and handle clipboard failures. Include an original title, description, and favicon; do not invent an active production URL.

Validate mobile and desktop sizes, check local links, and test tabs and Copy. Deliver files, preview/deployment instructions, real screenshots, and a short list of unverified items. Prepare everything for review before publishing. Do not add features beyond this landing page.
