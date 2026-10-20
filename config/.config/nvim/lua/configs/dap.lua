local dap, ui = require "dap", require "dapui"
local project = require "workbench.project"
local mason = vim.fn.stdpath "data" .. "/mason"
vim.fn.sign_define("DapBreakpoint", { text = "●", texthl = "DiagnosticError" })
vim.fn.sign_define("DapBreakpointCondition", { text = "◆", texthl = "DiagnosticWarn" })
vim.fn.sign_define("DapStopped", { text = "▶", texthl = "DiagnosticOk", linehl = "Visual" })
ui.setup {
  icons = { expanded = "▾", collapsed = "▸", current_frame = "▶" },
  layouts = {
    {
      elements = {
        { id = "scopes", size = 0.5 },
        { id = "breakpoints", size = 0.2 },
        { id = "stacks", size = 0.3 },
      },
      size = 36,
      position = "left",
    },
    {
      elements = { { id = "repl", size = 0.5 }, { id = "console", size = 0.5 } },
      size = 10,
      position = "bottom",
    },
  },
  floating = { border = "rounded" },
}
dap.listeners.after.event_initialized.workbench = function()
  ui.open()
end
dap.listeners.before.event_terminated.workbench = function()
  ui.close()
end
dap.listeners.before.event_exited.workbench = function()
  ui.close()
end
dap.adapters.python = {
  type = "executable",
  command = mason .. "/packages/debugpy/venv/bin/python",
  args = { "-m", "debugpy.adapter" },
}
dap.configurations.python = {
  {
    type = "python",
    request = "launch",
    name = "Python · archivo actual",
    program = "${file}",
    cwd = project.root,
    pythonPath = function()
      return project.python()
    end,
    console = "integratedTerminal",
    justMyCode = true,
  },
  {
    type = "python",
    request = "launch",
    name = "Python · pytest del archivo",
    module = "pytest",
    args = { "${file}", "-s" },
    cwd = project.root,
    pythonPath = function()
      return project.python()
    end,
    console = "integratedTerminal",
    justMyCode = false,
  },
}
dap.adapters.codelldb = {
  type = "server",
  -- Cold starts on slower disks can exceed the default 3.5-second connection window.
  options = { max_retries = 60 },
  port = "${port}",
  executable = { command = mason .. "/bin/codelldb", args = { "--port", "${port}" } },
}
dap.configurations.cpp = {
  {
    type = "codelldb",
    request = "launch",
    name = "C/C++ · ejecutar binario",
    program = function()
      local binary = require("workbench.tasks").artifact(vim.api.nvim_buf_get_name(0))
      local default = vim.fn.executable(binary) == 1 and binary or (project.root() .. "/build/")
      local path = vim.fn.input("Binario con símbolos (-g): ", default, "file")
      return path ~= "" and vim.fn.fnamemodify(path, ":p") or dap.ABORT
    end,
    cwd = project.root,
    stopOnEntry = false,
    expressions = "native",
  },
}
dap.configurations.c = vim.deepcopy(dap.configurations.cpp)
dap.adapters["pwa-node"] = {
  type = "server",
  host = "127.0.0.1",
  port = "${port}",
  executable = { command = mason .. "/bin/js-debug-adapter", args = { "${port}", "127.0.0.1" } },
}
local node = {
  {
    type = "pwa-node",
    request = "launch",
    name = "Node · archivo actual",
    program = "${file}",
    cwd = project.root,
    sourceMaps = true,
    console = "integratedTerminal",
    skipFiles = { "<node_internals>/**" },
    resolveSourceMapLocations = { "${workspaceFolder}/**", "!**/node_modules/**" },
  },
  {
    type = "pwa-node",
    request = "attach",
    name = "Node · adjuntar a proceso",
    processId = require("dap.utils").pick_process,
    cwd = project.root,
    sourceMaps = true,
    skipFiles = { "<node_internals>/**" },
  },
}
for _, ft in ipairs { "javascript", "typescript", "javascriptreact", "typescriptreact" } do
  dap.configurations[ft] = vim.deepcopy(node)
end
