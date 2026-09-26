local opts = require "nvchad.configs.telescope"
local actions = require "telescope.actions"
opts.defaults = vim.tbl_deep_extend("force", opts.defaults, {
  prompt_prefix = "   ",
  selection_caret = "› ",
  entry_prefix = "  ",
  border = true,
  path_display = { "smart" },
  layout_strategy = "flex",
  layout_config = {
    width = 0.9,
    height = 0.84,
    horizontal = { prompt_position = "top", preview_width = 0.52, preview_cutoff = 120 },
    vertical = {
      prompt_position = "top",
      preview_height = 0.38,
      mirror = true,
      preview_cutoff = 20,
    },
    flex = { flip_columns = 120, flip_lines = 20 },
  },
  preview = { filesize_limit = 1, timeout = 200 },
  results_title = "Resultados",
  file_ignore_patterns = {
    "node_modules/",
    "%.git/",
    "%.venv/",
    "__pycache__/",
    "dist/",
    "build/",
    "%.next/",
    "coverage/",
  },
  vimgrep_arguments = {
    "rg",
    "--color=never",
    "--no-heading",
    "--with-filename",
    "--line-number",
    "--column",
    "--smart-case",
    "--hidden",
    "--glob",
    "!.git/*",
  },
  mappings = {
    i = {
      ["<C-j>"] = actions.move_selection_next,
      ["<C-k>"] = actions.move_selection_previous,
      ["<C-q>"] = actions.send_selected_to_qflist + actions.open_qflist,
      ["<C-u>"] = actions.preview_scrolling_up,
      ["<C-d>"] = actions.preview_scrolling_down,
    },
    n = { q = actions.close },
  },
})
opts.pickers = {
  find_files = {
    hidden = true,
    find_command = {
      "rg",
      "--files",
      "--hidden",
      "--glob",
      "!.git",
      "--glob",
      "!node_modules",
      "--glob",
      "!.venv",
    },
  },
  buffers = {
    sort_mru = true,
    ignore_current_buffer = true,
    mappings = { i = { ["<C-x>"] = actions.delete_buffer } },
  },
}
opts.extensions = {
  fzf = {
    fuzzy = true,
    override_generic_sorter = true,
    override_file_sorter = true,
    case_mode = "smart_case",
  },
  ["ui-select"] = require("telescope.themes").get_dropdown {
    previewer = false,
    layout_config = { width = 0.64, height = 0.4 },
  },
}
opts.extensions_list = { "themes", "terms", "fzf", "ui-select" }
return opts
