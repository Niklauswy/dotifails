return {
  { "nvchad/ui", pin = true },
  { "nvchad/base46", pin = true },
  {
    "stevearc/conform.nvim",
    event = "BufWritePre",
    cmd = "ConformInfo",
    opts = function()
      return require "configs.conform"
    end,
  },
  {
    "neovim/nvim-lspconfig",
    pin = true,
    config = function()
      require "configs.lspconfig"
    end,
  },
  {
    "mason-org/mason.nvim",
    opts = {
      ui = {
        border = "rounded",
        height = 0.82,
        icons = {
          package_installed = "✓",
          package_pending = "◌",
          package_uninstalled = "○",
        },
      },
      max_concurrent_installers = 3,
    },
  },
  {
    "nvim-treesitter/nvim-treesitter",
    branch = "master",
    pin = true,
    opts = {
      ensure_installed = {},
      auto_install = false,
      highlight = {
        enable = true,
        disable = function(_, buf)
          return vim.b[buf].large_file == true
        end,
      },
      indent = { enable = true, disable = { "python" } },
      incremental_selection = {
        enable = true,
        keymaps = {
          init_selection = "<C-Space>",
          node_incremental = "<C-Space>",
          node_decremental = "<BS>",
        },
      },
    },
  },
  {
    "hrsh7th/nvim-cmp",
    opts = function()
      local opts = require "nvchad.configs.cmp"
      local cmp = require "cmp"
      opts.preselect = cmp.PreselectMode.None
      opts.completion.completeopt = "menu,menuone,noselect"
      opts.mapping["<CR>"] = cmp.mapping.confirm { select = false }
      opts.sources = {
        { name = "nvim_lsp", priority = 1000 },
        { name = "luasnip", priority = 750 },
        { name = "async_path", priority = 500 },
        {
          name = "buffer",
          keyword_length = 3,
          option = {
            get_bufnrs = function()
              return vim.b.large_file and {} or { vim.api.nvim_get_current_buf() }
            end,
          },
        },
      }
      return opts
    end,
  },
  {
    "nvim-telescope/telescope.nvim",
    pin = true,
    init = function()
      local original, wrapper = vim.ui.select
      wrapper = function(...)
        local ok = pcall(require, "telescope")
        local select = vim.ui.select
        if not ok or select == wrapper then
          select = original
        end
        return select(...)
      end
      vim.ui.select = wrapper
    end,
    dependencies = {
      { "nvim-telescope/telescope-fzf-native.nvim", build = "make" },
      "nvim-telescope/telescope-ui-select.nvim",
    },
    opts = function()
      return require "configs.telescope"
    end,
    config = function(_, opts)
      local telescope = require "telescope"
      telescope.setup(opts)
      for _, name in ipairs { "fzf", "ui-select", "themes", "terms" } do
        telescope.load_extension(name)
      end
    end,
  },
  {
    "nvim-tree/nvim-tree.lua",
    opts = function()
      local opts = require "nvchad.configs.nvimtree"
      opts.view.width = 32
      opts.renderer.root_folder_label = ":t"
      opts.renderer.group_empty = true
      opts.diagnostics = { enable = true, show_on_dirs = true }
      opts.filters = {
        dotfiles = false,
        custom = { "^\\.git$", "^node_modules$", "^__pycache__$", "^\\.venv$" },
      }
      return opts
    end,
  },
  {
    "folke/which-key.nvim",
    opts = {
      preset = "modern",
      delay = 300,
      spec = {
        { "<leader>c", group = "Código" },
        { "<leader>d", group = "Depuración / diagnósticos" },
        { "<leader>f", group = "Buscar" },
        { "<leader>g", group = "Git" },
        { "<leader>p", group = "Herramientas" },
        { "<leader>q", group = "Sesiones" },
        { "<leader>r", group = "Ejecutar / proyecto" },
        { "<leader>u", group = "Interfaz" },
        { "<leader>w", group = "Espacios de trabajo" },
      },
    },
  },
  { "folke/trouble.nvim", cmd = "Trouble", opts = { focus = true, warn_no_results = false } },
  { "sindrets/diffview.nvim", cmd = { "DiffviewOpen", "DiffviewFileHistory", "DiffviewClose" } },
  { "nvim-mini/mini.surround", version = "v0.16.0", event = "User FilePost", opts = {} },
  { "nvim-mini/mini.ai", version = "v0.16.0", event = "User FilePost", opts = { n_lines = 300 } },
  { "folke/persistence.nvim", event = "BufReadPre", opts = {} },
  {
    "mfussenegger/nvim-dap",
    version = "0.10.0",
    dependencies = { "rcarriga/nvim-dap-ui", "nvim-neotest/nvim-nio" },
    config = function()
      require "configs.dap"
    end,
  },
}
