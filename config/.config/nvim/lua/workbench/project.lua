local M = { interpreters = {} }
M.markers = {
  "package.json",
  "pyproject.toml",
  "setup.cfg",
  "requirements.txt",
  "CMakeLists.txt",
  "Makefile",
  ".git",
}
function M.root(buf)
  if type(buf) ~= "number" then
    buf = 0
  end
  local name = vim.api.nvim_buf_get_name(buf or 0)
  if name == "" or vim.bo[buf or 0].buftype ~= "" then
    return vim.uv.cwd()
  end
  local directory = vim.fs.dirname(name)
  local root = vim.fs.root(name, M.markers)
  if root == vim.env.HOME and directory ~= root then
    root = nil
  end
  return root or directory or vim.uv.cwd()
end
function M.python(root)
  root = root or M.root()
  local candidates = {
    M.interpreters[root],
    vim.env.VIRTUAL_ENV and (vim.env.VIRTUAL_ENV .. "/bin/python"),
    root .. "/.venv/bin/python",
    root .. "/venv/bin/python",
    vim.fn.exepath "python3",
  }
  -- Sparse tables need explicit traversal: an unset selected interpreter is normal.
  for i = 1, 5 do
    local path = candidates[i]
    if path and vim.fn.executable(path) == 1 then
      return path
    end
  end
  return "python3"
end
function M.select_python()
  local root = M.root()
  vim.ui.input(
    { prompt = "Intérprete Python: ", default = M.python(root), completion = "file" },
    function(path)
      if not path or path == "" then
        return
      end
      path = vim.fn.fnamemodify(vim.fn.expand(path), ":p")
      if vim.fn.executable(path) ~= 1 then
        return vim.notify("El intérprete no es ejecutable.", vim.log.levels.ERROR)
      end
      M.interpreters[root] = path
      for _, client in ipairs(vim.lsp.get_clients { name = "pyright" }) do
        if client.config.root_dir == root then
          client.config.settings.python.pythonPath = path
          client:notify("workspace/didChangeConfiguration", { settings = client.config.settings })
        end
      end
      vim.notify("Python: " .. path)
    end
  )
end
function M.files()
  require("telescope.builtin").find_files {
    cwd = M.root(),
    prompt_title = "Archivos · " .. vim.fs.basename(M.root()),
  }
end
function M.grep()
  require("telescope.builtin").live_grep { cwd = M.root(), prompt_title = "Texto en el proyecto" }
end
function M.word()
  require("telescope.builtin").grep_string { cwd = M.root(), word_match = "-w" }
end
function M.cwd()
  local root = M.root()
  vim.cmd.cd(vim.fn.fnameescape(root))
  vim.notify("Proyecto: " .. root)
end
function M.package(root)
  local ok, lines = pcall(vim.fn.readfile, root .. "/package.json")
  if not ok then
    return {}
  end
  local valid, data = pcall(vim.json.decode, table.concat(lines, "\n"))
  return valid and type(data) == "table" and data or {}
end
function M.manager(root)
  local declared = M.package(root).packageManager or ""
  if type(declared) ~= "string" then
    declared = ""
  end
  for _, name in ipairs { "pnpm", "yarn", "bun", "npm" } do
    if declared:match("^" .. name .. "@") then
      return name
    end
  end
  local lock = vim.fs.find(
    { "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb", "package-lock.json" },
    { path = root, upward = true }
  )[1] or ""
  if lock:match "pnpm%-lock" then
    return "pnpm"
  end
  if lock:match "yarn%.lock" then
    return "yarn"
  end
  if lock:match "bun%.lock" then
    return "bun"
  end
  return "npm"
end
return M
