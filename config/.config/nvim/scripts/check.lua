local fixture_root = vim.env.NVIM_CHECK_ROOT or "/tmp/nvim-workbench-check"
vim.opt.swapfile = false
vim.opt.undofile = false
vim.opt.shadafile = "NONE"
require("persistence").stop()
local results = {}
local function check(name, fn)
  local ok, err = pcall(fn)
  results[#results + 1] = { name = name, passed = ok, error = not ok and tostring(err) or nil }
  print((ok and "PASS " or "FAIL ") .. name .. (not ok and (" " .. tostring(err)) or ""))
end
vim.g.ui_entered = true
vim.cmd.cd(fixture_root)
local function edit(file)
  vim.cmd("edit! " .. vim.fn.fnameescape(fixture_root .. "/" .. file))
  vim.wait(150, function()
    return false
  end, 30)
  return vim.api.nvim_get_current_buf()
end
check("Carga, comandos y atajos", function()
  require "mappings"
  assert(vim.fn.exists ":NvimHealth" == 2)
  assert(vim.fn.maparg("<Space>rr", "n") ~= "")
  assert(vim.fn.maparg("<C-s>", "i") ~= "")
  assert(require("nvconfig").base46.transparency)
end)
for _, case in ipairs {
  { file = "check.ts", servers = { "ts_ls" } },
  { file = "check.py", servers = { "pyright", "ruff" } },
  { file = "check.cpp", servers = { "clangd" } },
} do
  check("LSP y diagnósticos · " .. case.file, function()
    local buf = edit(case.file)
    assert(
      vim.wait(25000, function()
        for _, name in ipairs(case.servers) do
          local c = vim.lsp.get_clients({ bufnr = buf, name = name })[1]
          if not c or not c.initialized then
            return false
          end
        end
        return #vim.diagnostic.get(buf, { severity = vim.diagnostic.severity.ERROR }) > 0
      end, 100),
      "No hubo diagnóstico de error o faltó un servidor"
    )
    if case.file == "check.py" then
      local c = vim.lsp.get_clients({ bufnr = buf, name = "pyright" })[1]
      assert(c.config.settings.python.pythonPath:match "python")
    end
    if case.file == "check.ts" then
      local c = vim.lsp.get_clients({ bufnr = buf, name = "ts_ls" })[1]
      local response = c:request_sync("textDocument/definition", {
        textDocument = { uri = vim.uri_from_bufnr(buf) },
        position = { line = 4, character = 16 },
      }, 5000, buf)
      assert(
        response and response.result and #response.result > 0,
        "La navegación a definición falló"
      )
      assert(c.server_capabilities.completionProvider, "Falta autocompletado")
    end
  end)
end
for _, case in ipairs {
  {
    ft = "javascript",
    ext = "js",
    input = "const answer={number:42,label:'ok'}",
    contains = "const answer = {",
  },
  { ft = "python", ext = "py", input = "def add(a,b):\n return a+b", contains = "def add(a, b):" },
  { ft = "cpp", ext = "cpp", input = "int main(){int n=42;return n;}", contains = "int n = 42;" },
} do
  check("Formato · " .. case.ft, function()
    vim.cmd.enew { bang = true }
    vim.api.nvim_buf_set_name(0, fixture_root .. "/format." .. case.ext)
    vim.bo.filetype = case.ft
    vim.api.nvim_buf_set_lines(0, 0, -1, false, vim.split(case.input, "\n"))
    local err
    require("conform").format(
      { async = false, timeout_ms = 8000, lsp_format = "never" },
      function(e)
        err = e
      end
    )
    assert(not err, tostring(err))
    local content = table.concat(vim.api.nvim_buf_get_lines(0, 0, -1, false), "\n")
    assert(content:find(case.contains, 1, true), content)
    vim.bo.modified = false
  end)
end
check("Fuzzy nativo y selector", function()
  require "telescope"
  assert(require("telescope._extensions").manager.fzf)
  assert(require("telescope._extensions").manager["ui-select"])
  local lib = require "fzf_lib"
  assert(lib)
  local out = vim.system({ "rg", "--files" }, { cwd = fixture_root, text = true }):wait()
  assert(out.code == 0 and out.stdout:find("check.ts", 1, true))
end)
check("Proyecto y tareas", function()
  edit "check.ts"
  local p = require "workbench.project"
  assert(p.root() == fixture_root)
  assert(p.manager(p.root()) == "npm")
  assert(p.package(p.root()).scripts.test == "node debug.js")
  assert(vim.fn.executable(p.python(p.root())) == 1)
  local entries
  local old = vim.ui.select
  vim.ui.select = function(items)
    entries = items
  end
  require("workbench.tasks").menu()
  vim.ui.select = old
  assert(entries and entries[1].argv[1] == "npm")
end)
check("DAP, interfaz y adaptadores", function()
  require "dap"
  local dap = require "dap"
  for _, name in ipairs { "python", "cpp", "c", "javascript", "typescript" } do
    assert(#dap.configurations[name] > 0)
  end
  assert(vim.fn.executable(dap.adapters.python.command) == 1)
  assert(vim.fn.executable(dap.adapters.codelldb.executable.command) == 1)
  assert(vim.fn.executable(dap.adapters["pwa-node"].executable.command) == 1)
  require("dapui").open()
  require("dapui").close()
end)
check("Interfaces bajo demanda", function()
  require("lazy").load {
    plugins = { "nvim-tree.lua", "trouble.nvim", "diffview.nvim", "which-key.nvim" },
  }
  vim.cmd.NvimTreeOpen()
  vim.cmd.NvimTreeClose()
  require("trouble").open { mode = "diagnostics", focus = false }
  require("trouble").close()
  assert(require "diffview")
end)
for _, client in ipairs(vim.lsp.get_clients()) do
  client:stop(true)
end
vim.fn.writefile({ vim.json.encode(results) }, fixture_root .. "/results.json")
local failed = vim.tbl_filter(function(r)
  return not r.passed
end, results)
if #failed > 0 then
  vim.cmd "cquit 1"
else
  vim.cmd "qa!"
end
