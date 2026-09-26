local function web(buf)
  local root = vim.fs.root(buf, { "biome.json", "biome.jsonc" })
  if root and require("conform").get_formatter_info("biome", buf).available then
    return { "biome" }
  end
  return { "prettier" }
end
return {
  formatters_by_ft = {
    lua = { "stylua" },
    javascript = web,
    javascriptreact = web,
    typescript = web,
    typescriptreact = web,
    json = web,
    jsonc = web,
    css = web,
    html = { "prettier" },
    scss = { "prettier" },
    yaml = { "prettier" },
    markdown = { "prettier" },
    graphql = { "prettier" },
    python = { "ruff_format" },
    c = { "clang-format" },
    cpp = { "clang-format" },
  },
  default_format_opts = { lsp_format = "fallback" },
  format_on_save = function(buf)
    if
      vim.g.disable_autoformat
      or vim.b[buf].disable_autoformat
      or vim.b[buf].large_file
      or vim.bo[buf].buftype ~= ""
    then
      return
    end
    return { timeout_ms = 1000, lsp_format = "fallback" }
  end,
  notify_on_error = true,
  notify_no_formatters = false,
}
