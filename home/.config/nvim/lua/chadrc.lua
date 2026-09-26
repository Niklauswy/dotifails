---@type ChadrcConfig
local M = {}
M.base46 = {
  theme = "rosepine",
  transparency = true,
  theme_toggle = { "rosepine", "one_light" },
  changed_themes = {
    rosepine = {
      base_30 = { grey_fg = "#6e6a86", grey_fg2 = "#908caa", light_grey = "#908caa" },
      base_16 = { base07 = "#908caa", base0B = "#9ccfd8", base0F = "#908caa" },
    },
  },
  integrations = { "dap", "trouble" },
  hl_override = {
    Comment = { fg = "#908caa", italic = true },
    LineNr = { fg = "#6e6a86" },
    NvDashButtons = { fg = "#e0def4" },
    NvDashFooter = { fg = "#908caa" },
    St_file_txt = { fg = "#e0def4", bg = "NONE" },
    St_cwd_txt = { fg = "#908caa", bg = "NONE" },
    St_Lsp = { fg = "#9ccfd8", bg = "NONE" },
    NormalFloat = { bg = "#1F1D2E" },
    FloatBorder = { fg = "#524F67", bg = "#1F1D2E" },
    TelescopeNormal = { bg = "#191724" },
    TelescopeBorder = { fg = "#524F67", bg = "#191724" },
    TelescopePromptNormal = { bg = "#26233A" },
    TelescopePromptBorder = { fg = "#524F67", bg = "#26233A" },
    TelescopePromptTitle = { fg = "#c4a7e7", bg = "#26233A", bold = true },
    TelescopeResultsTitle = { fg = "#908caa", bg = "#191724" },
    TelescopePreviewTitle = { fg = "#9ccfd8", bg = "#191724" },
    TelescopeSelection = { bg = "#2a273f" },
    CursorLine = { bg = "#26233A" },
  },
}
local function escape(s)
  return s:gsub("%%", "%%%%")
end
M.ui = {
  telescope = { style = "bordered" },
  cmp = { style = "flat_dark", icons_left = true, abbr_maxwidth = 44 },
  tabufline = { lazyload = false, bufwidth = 26, order = { "treeOffset", "buffers", "tabs" } },
  statusline = {
    theme = "minimal",
    separator_style = "round",
    order = { "mode", "file", "git", "%=", "diagnostics", "lsp", "format", "cursor" },
    modules = {
      file = function()
        if vim.b.workbench_task then
          local code = vim.b.workbench_exit_code
          local state = code == nil and "en curso"
            or (code == 0 and "completado" or ("salida " .. code))
          return "%#St_file_txt# " .. escape(vim.b.workbench_task) .. " · " .. state .. "  "
        end
        if vim.bo.filetype == "TelescopePrompt" then
          return "%#St_file_txt#  Buscar  "
        end
        if vim.bo.filetype == "nvdash" then
          return "%#St_file_txt#  Inicio  "
        end
        local name = vim.fn.expand "%:~:."
        if name == "" then
          name = "Sin título"
        end
        local length = vim.fn.strchars(name)
        if length > 44 then
          name = "…" .. vim.fn.strcharpart(name, length - 41)
        end
        return "%#St_file_txt# "
          .. escape(name)
          .. (vim.bo.modified and " ●" or "")
          .. (vim.bo.readonly and " " or "")
          .. "  "
      end,
      lsp = function()
        if vim.o.columns < 95 then
          return ""
        end
        local names = {}
        for _, client in ipairs(vim.lsp.get_clients { bufnr = 0 }) do
          names[#names + 1] = client.name
        end
        table.sort(names)
        return #names > 0 and ("%#St_Lsp# 󰒋 " .. escape(table.concat(names, " · ")) .. "  ")
          or ""
      end,
      format = function()
        if vim.o.columns < 90 or vim.bo.buftype ~= "" then
          return ""
        end
        return "%#St_cwd_txt# "
          .. ((vim.g.disable_autoformat or vim.b.disable_autoformat) and "FMT —" or "FMT ✓")
          .. "  "
      end,
      cursor = function()
        if vim.b.workbench_task then
          local hint = vim.b.workbench_exit_code ~= nil and "gg inicio · G final · q cerrar"
            or "Ctrl+X explorar"
          return "%#St_cwd_txt# "
            .. (vim.api.nvim_win_get_width(0) >= 85 and hint .. "  " or "")
            .. "%l/%L  "
        end
        if vim.bo.buftype ~= "" then
          return ""
        end
        return "%#St_Lsp# %l:%c  %#St_cwd_txt#%p%%  "
      end,
    },
  },
}
M.nvdash = {
  load_on_startup = true,
  header = {
    "                                  ",
    "            N E O V I M          ",
    "                                  ",
    "    JS / TS    C / C++    PYTHON   ",
    "                                  ",
  },
  buttons = {
    { txt = "  Buscar archivos", keys = "ff", cmd = "lua require('workbench.project').files()" },
    {
      txt = "󰈭  Buscar en el proyecto",
      keys = "fw",
      cmd = "lua require('workbench.project').grep()",
    },
    { txt = "  Archivos recientes", keys = "fo", cmd = "Telescope oldfiles" },
    { txt = "󰁯  Recuperar sesión", keys = "qs", cmd = "lua require('persistence').load()" },
    { txt = "  Guía y atajos", keys = "?", cmd = "NvimGuide" },
    { txt = "󰒓  Herramientas instaladas", keys = "pm", cmd = "Mason" },
    { txt = "─", hl = "NvDashFooter", no_gap = true, rep = true },
    {
      txt = "ESPACIO abre los comandos · :NvimHealth revisa el entorno",
      hl = "NvDashFooter",
      no_gap = true,
    },
  },
}
M.term = { float = { border = "rounded", width = 0.82, height = 0.68, row = 0.12, col = 0.09 } }
return M
