local M = {}
local project = require "workbench.project"
function M.terminal(argv, cwd, title)
  if vim.fn.executable(argv[1]) ~= 1 then
    return vim.notify("No está disponible: " .. argv[1], vim.log.levels.ERROR)
  end
  M.last = { argv = vim.deepcopy(argv), cwd = cwd, title = title }
  vim.cmd("botright " .. math.max(8, math.floor(vim.o.lines * 0.3)) .. "new")
  local buf = vim.api.nvim_get_current_buf()
  vim.bo[buf].bufhidden = "hide"
  vim.b[buf].workbench_task = title or "Tarea"
  vim.keymap.set("t", "<Esc>", "<C-\\><C-N>", { buffer = buf, desc = "Explorar salida" })
  vim.keymap.set("n", "q", "<cmd>hide<cr>", { buffer = buf, desc = "Cerrar panel de salida" })
  -- Re-entering a finished terminal must not arm Neovim's 'any key closes' behavior.
  vim.api.nvim_create_autocmd("TermEnter", {
    buffer = buf,
    callback = function()
      if vim.b[buf].workbench_exit_code ~= nil then
        vim.cmd.stopinsert()
      end
    end,
  })
  M.job = vim.fn.termopen(argv, {
    cwd = cwd,
    on_exit = function(_, code)
      vim.schedule(function()
        if vim.api.nvim_buf_is_valid(buf) then
          vim.b[buf].workbench_exit_code = code
          -- Leave other windows (including another interactive terminal) alone.
          if vim.api.nvim_get_current_buf() == buf then
            vim.cmd.stopinsert()
          end
          vim.cmd.redrawstatus()
        end
        vim.notify(
          (title or "Tarea") .. (code == 0 and " · completado" or (" · salida " .. code)),
          code == 0 and vim.log.levels.INFO or vim.log.levels.WARN
        )
      end)
    end,
  })
  vim.cmd.startinsert()
  return buf, M.job
end
function M.artifact(file)
  local dir = vim.fn.stdpath "cache" .. "/workbench-build"
  vim.fn.mkdir(dir, "p", "0700")
  return dir .. "/" .. vim.fn.sha256(file):sub(1, 12) .. "-" .. vim.fn.fnamemodify(file, ":t:r")
end
function M.compile(file, callback)
  local cpp = vim.bo.filetype == "cpp"
    or file:match "%.cpp$"
    or file:match "%.cc$"
    or file:match "%.cxx$"
  local output = M.artifact(file)
  local argv = {
    cpp and "g++" or "gcc",
    "-g",
    "-O0",
    "-Wall",
    "-Wextra",
    cpp and "-std=c++20" or "-std=c17",
    file,
    "-o",
    output,
  }
  if vim.fn.executable(argv[1]) ~= 1 then
    return vim.notify("Falta " .. argv[1], vim.log.levels.ERROR)
  end
  vim.notify("Compilando " .. vim.fs.basename(file) .. "…")
  vim.system(argv, { text = true, cwd = project.root() }, function(result)
    vim.schedule(function()
      if result.code == 0 then
        if callback then
          callback(output)
        else
          vim.notify("Compilado con símbolos de depuración: " .. output)
        end
      else
        vim.fn.setqflist({}, " ", {
          title = "Compilación",
          lines = vim.split(result.stderr or "", "\n"),
          efm = vim.o.errorformat,
        })
        vim.cmd.copen()
        vim.notify("La compilación encontró errores.", vim.log.levels.ERROR)
      end
    end)
  end)
end
function M.run_file()
  local file = vim.api.nvim_buf_get_name(0)
  if file == "" then
    return vim.notify("Guarda primero el archivo.", vim.log.levels.WARN)
  end
  vim.cmd.update()
  local ft, root = vim.bo.filetype, project.root()
  if ft == "c" or ft == "cpp" then
    M.compile(file, function(binary)
      M.terminal({ binary }, root, "Ejecutar C/C++")
    end)
  elseif ft == "python" then
    M.terminal({ project.python(root), file }, root, "Python")
  elseif ft == "javascript" or ft == "typescript" then
    M.terminal({ "node", file }, root, "Node")
  elseif ft == "sh" then
    M.terminal({ "bash", file }, root, "Bash")
  else
    vim.notify("Usa las tareas del proyecto con Espacio rr para este formato.", vim.log.levels.INFO)
  end
end
function M.menu()
  local root, choices = project.root(), {}
  local pkg = project.package(root)
  local scripts = type(pkg.scripts) == "table" and pkg.scripts or {}
  for name, command in pairs(scripts) do
    if type(command) == "string" then
      choices[#choices + 1] =
        { label = name .. "  ·  " .. command, argv = { project.manager(root), "run", name } }
    end
  end
  table.sort(choices, function(a, b)
    return a.label < b.label
  end)
  if vim.fn.filereadable(root .. "/pyproject.toml") == 1 or vim.bo.filetype == "python" then
    choices[#choices + 1] =
      { label = "Python · pytest del proyecto", argv = { project.python(root), "-m", "pytest" } }
    choices[#choices + 1] =
      { label = "Python · comprobar con Ruff", argv = { "ruff", "check", "." } }
  end
  if vim.fn.filereadable(root .. "/CMakeLists.txt") == 1 then
    choices[#choices + 1] = {
      label = "CMake · configurar build y compile_commands.json",
      argv = {
        "cmake",
        "-S",
        ".",
        "-B",
        "build",
        "-DCMAKE_BUILD_TYPE=Debug",
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
      },
    }
    choices[#choices + 1] =
      { label = "CMake · compilar", argv = { "cmake", "--build", "build", "-j", "2" } }
    choices[#choices + 1] = {
      label = "CMake · pruebas",
      argv = { "ctest", "--test-dir", "build", "--output-on-failure" },
    }
  end
  if vim.fn.filereadable(root .. "/Makefile") == 1 then
    choices[#choices + 1] = { label = "Make · compilar", argv = { "make", "-j2" } }
  end
  choices[#choices + 1] = { label = "Ejecutar el archivo actual", fn = M.run_file }
  if vim.bo.filetype == "c" or vim.bo.filetype == "cpp" then
    choices[#choices + 1] = {
      label = "C/C++ · compilar archivo para depurar",
      fn = function()
        vim.cmd.update()
        M.compile(vim.api.nvim_buf_get_name(0))
      end,
    }
  end
  vim.ui.select(choices, {
    prompt = "Tareas · " .. vim.fs.basename(root),
    format_item = function(item)
      return item.label
    end,
  }, function(item)
    if not item then
      return
    end
    if item.fn then
      item.fn()
    else
      M.terminal(item.argv, root, item.label)
    end
  end)
end
function M.test_file()
  if vim.bo.filetype == "python" then
    vim.cmd.update()
    local root = project.root()
    M.terminal(
      { project.python(root), "-m", "pytest", vim.api.nvim_buf_get_name(0), "-q" },
      root,
      "pytest · archivo"
    )
  else
    M.menu()
  end
end
function M.repeat_last()
  if M.last then
    M.terminal(M.last.argv, M.last.cwd, M.last.title)
  else
    M.menu()
  end
end
return M
