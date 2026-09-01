# InstaSave - Reels e Imagens do Instagram

Extensao para Chrome (Manifest V3) que detecta reels e imagens nas paginas do
Instagram, abre uma **janela de preview** com **contagem de tempo do reel**
(cronometro enquanto o video toca) e permite baixar com um clique.

## Funcionalidades

- Detecta automaticamente reels (videos) e fotos no feed, aba de reels e perfis.
- Painel flutuante (botao roxo) com a lista de midias encontradas.
- **Janela de preview**: abre a midia em tela cheia com play/pause, barra de
  progresso e cronometro `mm:ss / mm:ss` que conta o tempo de exibicao do reel.
- Botao de download por item e dentro do preview.
- Re-scan manual da pagina e atualizacao automatica ao rolar/navegar.
- Salva os arquivos em `Downloads/instagram/` como `reel_*.mp4` e `img_*.jpg`.

## Instalacao

1. Abra `chrome://extensions`.
2. Ative o **Modo do desenvolvedor** (canto superior direito).
3. Clique em **Carregar sem compactacao** e selecione a pasta
   `instagram-downloader/`.
4. Fixe a extensao na barra de ferramentas (icone de quebra-cabeca).

## Uso

1. Acesse `instagram.com` (feed, aba Reels ou um perfil) e role a pagina para
   carregar os posts.
2. Clique no botao flutuante com a seta para baixo (canto inferior direito).
3. O painel lista as midias detectadas (REEL ou FOTO).
   - **Clique na midia** para abrir o preview.
   - No preview de video, use o play/pause e acompanhe o cronometro do reel.
   - Clique em **Baixar** para salvar.
4. Alternativamente, use o icone da extensao (popup) para abrir o painel ou
   re-escanear a pagina.

## Estrutura

```
instagram-downloader/
├── manifest.json   # Configuracao MV3, permissoes e host permissions
├── background.js   # Service worker: busca a midia e inicia o download
├── content.js      # Deteccao de midia + painel + preview + cronometro
├── popup.html/js   # Popup da extensao
└── icons/          # Icones 16/48/128
```

## Observacoes

- Use apenas para conteudo que voce tem direito de baixar. Respeite os Termos
  de Uso do Instagram e os direitos autorais dos criadores.
- Alguns reels sao servidos via streaming (blob) e nao tem URL direta
  disponivel; nesse caso o InstaSave nao consegue baixa-los.
- O download usa a URL de midia detectada, que tem validade limitada. Se o
  download falhar, tente re-escanear a pagina e baixar novamente.
