-- Colours the first lines of a file exactly as the user's Neovim would: NvChad's compiled base46 highlights and
-- the installed treesitter parsers and queries. Run by nvim_theme.py as
--   nvim --clean --headless -l nvim_highlight.lua <file> <lines> <base46 cache dir> <nvim-treesitter dir>
-- Prints JSON {normal, lineNr, lines: [[[text, fg|null, italic], ...], ...], tabstop} or {"error": "..."}.
-- `--clean` keeps it fast and free of side effects: no user config, plugins or language servers.
local path, max, cache, ts = arg[1], tonumber(arg[2]) or 120, arg[3], arg[4]

local function finish(value)
  io.stdout:write(vim.json.encode(value))
  vim.cmd("qa!")
end

for _, f in ipairs({ "defaults", "syntax", "treesitter" }) do
  pcall(dofile, cache .. "/" .. f)
end
if ts and ts ~= "" then
  vim.opt.runtimepath:append(ts)
  vim.opt.runtimepath:append(ts .. "/runtime")
end

local handle = io.open(path, "rb")
if not handle then
  return finish({ error = "unreadable" })
end
local lines = {}
for line in handle:lines() do
  lines[#lines + 1] = line:gsub("\r$", "")
  if #lines >= max then
    break
  end
end
handle:close()

local buf = vim.api.nvim_create_buf(false, true)
vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
local ft = vim.filetype.match({ filename = path, buf = buf }) or ""
local lang = vim.treesitter.language.get_lang(ft) or ft
local ok, parser = pcall(vim.treesitter.get_parser, buf, lang)

-- Per byte: the highlight group that wins there.
local groups = {}
for i = 1, #lines do
  groups[i] = {}
end

local resolved = {}
local function colour(group)
  if not group then
    return nil, false
  end
  if resolved[group] == nil then
    -- "@keyword.function.bash" is drawn with the most specific group the theme defines, as Neovim does.
    local name, h = group, {}
    while name do
      h = vim.api.nvim_get_hl(0, { name = name, link = false })
      if h.fg then
        break
      end
      name = name:match("^(.+)%.[^.]+$")
    end
    resolved[group] = { h.fg and string.format("#%06x", h.fg) or false, h.italic or false }
  end
  return resolved[group][1] or nil, resolved[group][2]
end
local function apply(tree, ltree)
  local query = vim.treesitter.query.get(ltree:lang(), "highlights")
  if not query then
    return
  end
  local spans = {}
  for id, node, meta in query:iter_captures(tree:root(), buf, 0, #lines) do
    local name = query.captures[id]
    if name ~= "spell" and name ~= "nospell" and not name:match("^_") then
      local sr, sc, er, ec = node:range()
      spans[#spans + 1] = { sr, sc, er, ec, "@" .. name .. "." .. ltree:lang(), tonumber(meta.priority or (meta[id] and meta[id].priority)) or 100, #spans }
    end
  end
  table.sort(spans, function(a, b)
    return a[6] < b[6] or (a[6] == b[6] and a[7] < b[7])
  end)
  for _, s in ipairs(spans) do
    for row = s[1], math.min(s[3], #lines - 1) do
      local line = lines[row + 1]
      local from = row == s[1] and s[2] or 0
      local to = row == s[3] and s[4] or #line
      local g = groups[row + 1]
      -- A capture without colour (conceal, spell, ...) leaves what is under it, as extmarks combine.
      if colour(s[5]) then
        for c = from + 1, math.min(to, #line) do
          g[c] = s[5]
        end
      end
    end
  end
end
if ok and parser then
  -- Treesitter, as Neovim uses it whenever a parser is installed: captures applied in order (later and higher
  -- priority win), language injections on top of their host.
  parser:parse(true)
  parser:for_each_tree(apply)
elseif ft ~= "" then
  -- No parser (zsh, conf, ...): Neovim falls back to Vim's regex syntax, so read that instead.
  lang = "syntax:" .. ft
  vim.api.nvim_set_current_buf(buf)
  vim.cmd("syntax enable")
  vim.bo[buf].syntax = ft
  for row, line in ipairs(lines) do
    local g = groups[row]
    for c = 1, #line do
      local id = vim.fn.synIDtrans(vim.fn.synID(row, c, 1))
      local name = id > 0 and vim.fn.synIDattr(id, "name") or ""
      if name ~= "" and colour(name) then
        g[c] = name
      end
    end
  end
else
  return finish({ error = "unknown file type" })
end

local out = {}
for i, line in ipairs(lines) do
  local runs, g = {}, groups[i]
  local start, current = 1, nil
  for c = 1, #line + 1 do
    local here = g[c]
    if c > #line or here ~= current then
      if c > start then
        local fg, italic = colour(current)
        runs[#runs + 1] = { line:sub(start, c - 1), fg or vim.NIL, italic }
      end
      start, current = c, here
    end
  end
  out[i] = runs
end

local function fg(name)
  local h = vim.api.nvim_get_hl(0, { name = name, link = false })
  return h.fg and string.format("#%06x", h.fg) or vim.NIL
end
local normal = vim.api.nvim_get_hl(0, { name = "Normal", link = false })
finish({
  normal = fg("Normal"),
  bg = normal.bg and string.format("#%06x", normal.bg) or vim.NIL,
  lineNr = fg("LineNr"),
  lines = out,
  lang = lang,
})
