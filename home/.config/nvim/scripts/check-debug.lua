local fixture_root = vim.env.NVIM_CHECK_ROOT or "/tmp/nvim-workbench-check"
vim.opt.swapfile = false
vim.opt.undofile = false
vim.opt.shadafile = "NONE"
require("persistence").stop()
local lang = vim.env.NVIM_CHECK_LANG or "python"
local file = ({ python = "debug.py", javascript = "debug.js", cpp = "debug.cpp" })[lang]
local line = lang == "cpp" and 4 or 2
local result = { language = lang }
vim.g.ui_entered = true
vim.cmd.cd(fixture_root)
vim.cmd("edit " .. file)
local dap = require "dap"
vim.api.nvim_win_set_cursor(0, { line, 0 })
dap.toggle_breakpoint()
local stops = 0
dap.listeners.after.event_stopped.workbench_check = function()
  stops = stops + 1
end
local config = vim.deepcopy(dap.configurations[lang][1])
config.name = "Prueba local " .. lang
config.cwd = fixture_root
if lang == "cpp" then
  config.program = fixture_root .. "/debug-bin"
end
local ok, err = pcall(function()
  dap.run(config)
  assert(
    vim.wait(20000, function()
      local s = dap.session()
      return stops > 0 and s and s.current_frame ~= nil
    end, 50),
    "No se alcanzó el breakpoint"
  )
  result.breakpoint = true
  result.before_line = dap.session().current_frame.line
  result.before_name = dap.session().current_frame.name
  local function evaluate(expression)
    local answer, finished
    local s = assert(dap.session())
    s:request(
      "evaluate",
      { expression = expression, context = "watch", frameId = s.current_frame.id },
      function(e, body)
        answer = not e and body and body.result or tostring(e)
        finished = true
      end
    )
    assert(
      vim.wait(5000, function()
        return finished
      end, 25),
      "Evaluate sin respuesta"
    )
    return answer
  end
  result.value = evaluate "value"
  assert(tostring(result.value):find("21", 1, true), "Valor incorrecto: " .. tostring(result.value))
  dap.step_over()
  assert(
    vim.wait(10000, function()
      local s = dap.session()
      return stops >= 2 and s and s.current_frame and s.current_frame.line > line
    end, 50),
    "Step over sin avance"
  )
  vim.wait(300, function()
    return false
  end, 25)
  result.after_line = dap.session().current_frame.line
  result.after_name = dap.session().current_frame.name
  result.doubled = evaluate "doubled"
  assert(tostring(result.doubled):find("42", 1, true), "Valor posterior incorrecto")
  result.stepped = true
end)
result.ok = ok
result.error = not ok and tostring(err) or nil
if dap.session() then
  dap.terminate()
end
vim.wait(3000, function()
  return dap.session() == nil
end, 50)
require("dapui").close()
for _, client in ipairs(vim.lsp.get_clients()) do
  client:stop(true)
end
vim.fn.writefile({ vim.json.encode(result) }, fixture_root .. "/dap-" .. lang .. ".json")
print(vim.json.encode(result))
if ok then
  vim.cmd "qa!"
else
  vim.cmd "cquit 1"
end
