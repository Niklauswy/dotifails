require "nvchad.autocmds"
local group = vim.api.nvim_create_augroup("Workbench", { clear = true })
vim.api.nvim_create_autocmd("BufReadPre", {
  group = group,
  callback = function(args)
    local stat = vim.uv.fs_stat(args.file)
    vim.b[args.buf].large_file = stat ~= nil and stat.size > 1024 * 1024
  end,
})
vim.api.nvim_create_autocmd("FileType", {
  group = group,
  pattern = { "python", "c", "cpp" },
  callback = function()
    -- Explicit .editorconfig settings are applied by Neovim after FileType.
    vim.opt_local.shiftwidth = 4
    vim.opt_local.softtabstop = 4
    vim.opt_local.tabstop = 4
  end,
})
vim.api.nvim_create_autocmd("TextYankPost", {
  group = group,
  callback = function()
    vim.highlight.on_yank { timeout = 140 }
  end,
})
vim.api.nvim_create_autocmd("BufReadPost", {
  group = group,
  callback = function(args)
    if vim.bo[args.buf].buftype ~= "" then
      return
    end
    local mark = vim.api.nvim_buf_get_mark(args.buf, '"')
    if mark[1] > 1 and mark[1] <= vim.api.nvim_buf_line_count(args.buf) then
      pcall(vim.api.nvim_win_set_cursor, 0, mark)
    end
  end,
})
vim.api.nvim_create_autocmd("FileType", {
  group = group,
  pattern = { "help", "qf", "checkhealth", "lspinfo" },
  callback = function(args)
    vim.keymap.set(
      "n",
      "q",
      "<cmd>close<cr>",
      { buffer = args.buf, silent = true, desc = "Cerrar panel" }
    )
  end,
})
vim.api.nvim_create_user_command("FormatToggle", function()
  vim.g.disable_autoformat = not vim.g.disable_autoformat
  vim.notify("Formato al guardar: " .. (vim.g.disable_autoformat and "pausado" or "activo"))
  vim.cmd.redrawstatus()
end, { desc = "Activar o pausar el formato al guardar" })
vim.api.nvim_create_user_command("NvimGuide", function()
  vim.cmd("tabnew " .. vim.fn.fnameescape(vim.fn.stdpath "config" .. "/README.md"))
end, {})
vim.api.nvim_create_user_command("NvimHealth", "checkhealth workbench", {})
vim.api.nvim_create_user_command("ProjectTasks", function()
  require("workbench.tasks").menu()
end, {})
vim.api.nvim_create_user_command("PythonSelect", function()
  require("workbench.project").select_python()
end, {})
