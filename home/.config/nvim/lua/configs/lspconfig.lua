require("nvchad.configs.lspconfig").defaults()
vim.lsp.config("*", { on_init = function() end })
vim.lsp.config("ts_ls", {
  root_dir = function(buf, on_dir)
    local root = require("workbench.project").root(buf)
    local deno = vim.fs.root(buf, { "deno.json", "deno.jsonc" })
    if deno and #deno >= #root then
      return
    end
    on_dir(root)
  end,
  init_options = {
    preferences = {
      includeCompletionsForModuleExports = true,
      includeCompletionsWithInsertText = true,
      importModuleSpecifierPreference = "shortest",
    },
  },
  -- Check standalone JavaScript too; explicit jsconfig/tsconfig settings take precedence.
  settings = { implicitProjectConfiguration = { checkJs = true } },
})
vim.lsp.config("pyright", {
  before_init = function(_, config)
    config.settings.python.pythonPath = require("workbench.project").python(config.root_dir)
  end,
  settings = {
    pyright = { disableOrganizeImports = true },
    python = {
      analysis = {
        autoSearchPaths = true,
        useLibraryCodeForTypes = true,
        diagnosticMode = "openFilesOnly",
        typeCheckingMode = "basic",
      },
    },
  },
})
vim.lsp.config("ruff", { init_options = { settings = { logLevel = "error" } } })
vim.lsp.config("clangd", {
  cmd = {
    "clangd",
    "--background-index",
    "--log=error",
    "--clang-tidy",
    "--completion-style=detailed",
    "--header-insertion=iwyu",
    "-j=2",
  },
})
vim.lsp.config("lua_ls", {
  settings = {
    Lua = {
      diagnostics = { globals = { "vim" } },
      workspace = { checkThirdParty = false },
      telemetry = { enable = false },
    },
  },
})
vim.lsp.enable { "ts_ls", "eslint", "pyright", "ruff", "clangd", "html", "cssls", "jsonls" }
vim.diagnostic.config {
  severity_sort = true,
  update_in_insert = false,
  underline = true,
  virtual_text = { spacing = 2, prefix = "●", severity = { min = vim.diagnostic.severity.WARN } },
  float = { border = "rounded", source = "if_many", focusable = false },
  signs = {
    text = {
      [vim.diagnostic.severity.ERROR] = "",
      [vim.diagnostic.severity.WARN] = "",
      [vim.diagnostic.severity.INFO] = "",
      [vim.diagnostic.severity.HINT] = "󰌵",
    },
  },
}
vim.api.nvim_create_autocmd("LspAttach", {
  group = vim.api.nvim_create_augroup("WorkbenchLsp", { clear = true }),
  callback = function(args)
    local client = vim.lsp.get_client_by_id(args.data.client_id)
    if not client then
      return
    end
    if client.name == "ruff" then
      client.server_capabilities.hoverProvider = false
    end
    if client.name == "ts_ls" or client.name == "eslint" then
      client.server_capabilities.documentFormattingProvider = false
      client.server_capabilities.documentRangeFormattingProvider = false
    end
    local function map(keys, fn, desc)
      vim.keymap.set("n", keys, fn, { buffer = args.buf, desc = desc })
    end
    map("gd", function()
      require("telescope.builtin").lsp_definitions()
    end, "Código: definición")
    map("gr", function()
      require("telescope.builtin").lsp_references()
    end, "Código: referencias")
    map("gi", function()
      require("telescope.builtin").lsp_implementations()
    end, "Código: implementaciones")
    map("K", vim.lsp.buf.hover, "Código: documentación")
    map("<leader>cr", vim.lsp.buf.rename, "Código: renombrar símbolo")
    map("<leader>ca", vim.lsp.buf.code_action, "Código: acciones")
    map("<leader>cs", function()
      require("telescope.builtin").lsp_document_symbols()
    end, "Código: símbolos")
    map("<leader>ci", function()
      vim.lsp.buf.code_action {
        context = { only = { "source.organizeImports" }, diagnostics = {} },
        apply = true,
      }
    end, "Código: organizar imports")
    if client.name == "clangd" then
      map("<leader>ch", "<cmd>LspClangdSwitchSourceHeader<cr>", "C/C++: alternar cabecera")
    end
  end,
})
