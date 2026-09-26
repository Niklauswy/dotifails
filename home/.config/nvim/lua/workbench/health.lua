local M = {}
function M.check()
  vim.health.start "Entorno de desarrollo"
  if vim.fn.has "nvim-0.11" == 1 then
    vim.health.ok "Neovim 0.11+: API LSP nativa"
  else
    vim.health.error "Se necesita Neovim 0.11+"
  end
  for _, name in ipairs {
    "node",
    "python3",
    "gcc",
    "g++",
    "make",
    "cmake",
    "git",
    "rg",
    "typescript-language-server",
    "vscode-eslint-language-server",
    "pyright-langserver",
    "ruff",
    "clangd",
    "lua-language-server",
    "prettier",
    "clang-format",
    "stylua",
    "codelldb",
    "js-debug-adapter",
  } do
    local path = vim.fn.exepath(name)
    if path ~= "" then
      vim.health.ok(name .. ": " .. path)
    else
      vim.health.error("Falta " .. name .. " · revisa :Mason")
    end
  end
  local debugpy = vim.fn.stdpath "data" .. "/mason/packages/debugpy/venv/bin/python"
  if vim.fn.executable(debugpy) == 1 then
    vim.health.ok "Adaptador debugpy instalado"
  else
    vim.health.error "Falta debugpy · :MasonInstall debugpy"
  end
  local native = vim.fn.stdpath "data" .. "/lazy/telescope-fzf-native.nvim/build/libfzf.so"
  if vim.uv.fs_stat(native) then
    vim.health.ok "Búsqueda fuzzy nativa compilada"
  else
    vim.health.error "Falta compilar fzf-native · :Lazy build telescope-fzf-native.nvim"
  end
  for _, lang in ipairs {
    "javascript",
    "typescript",
    "tsx",
    "python",
    "c",
    "cpp",
    "lua",
    "json",
    "html",
    "css",
    "markdown",
  } do
    local ok = pcall(vim.treesitter.language.add, lang)
    if ok then
      vim.health.ok("Parser: " .. lang)
    else
      vim.health.warn("Falta parser: " .. lang .. " · :TSInstall " .. lang)
    end
  end
  vim.health.info("Python del proyecto: " .. require("workbench.project").python())
  vim.health.info("Formato al guardar: " .. (vim.g.disable_autoformat and "pausado" or "activo"))
  vim.health.info "Las versiones de NvChad, LSP, Telescope y Treesitter están fijadas para Neovim 0.11.5."
end
return M
