"""Markdown parser and syntax tokenizer used by the Files preview (no GUI needed)."""
import sys
import unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if not (root/'apps/wysun').is_dir():root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'apps/wysun'))
from wysun_files import markdown
from wysun_files.highlight import language_for_fence, language_for_path, tokenize

INK=dict(link='#fff',code_bg='#111',code_fg='#eee',mono='mono',muted='#999')


class MarkdownTests(unittest.TestCase):
    def kinds(self,text):return [block['t'] for block in markdown.parse(text)]
    def test_headings_rules_and_setext(self):
        self.assertEqual(self.kinds('# A\n\n---\n\nTitle\n=====\n'),['heading','rule','heading'])
    def test_lists_do_not_merge_across_kinds(self):
        blocks=markdown.parse('- a\n- b\n\n1. one\n2. two\n')
        self.assertEqual([(b['t'],b['ordered']) for b in blocks],[('list',False),('list',True)])
    def test_nested_and_task_lists(self):
        block=markdown.parse('- [x] done\n- todo\n  - child\n')[0]
        self.assertTrue(block['items'][0]['task']);self.assertIsNone(block['items'][1]['task'])
        self.assertEqual(block['items'][1]['children'][1]['t'],'list')
    def test_table_with_alignment(self):
        block=markdown.parse('| a | b |\n|:-:|--:|\n| 1 | 2 |\n')[0]
        self.assertEqual((block['t'],block['align'],block['rows']),('table',['center','right'],[['1','2']]))
    def test_fenced_code_keeps_content_verbatim(self):
        block=markdown.parse('```py\nx = "# not a heading"\n```\n')[0]
        self.assertEqual((block['t'],block['lang'],block['text']),('code','py','x = "# not a heading"'))
    def test_quote_and_image(self):
        self.assertEqual(self.kinds('> quote\n\n![alt](pic.png)\n'),['quote','image'])
    def test_front_matter_is_split(self):
        front,body=markdown.split_front_matter('---\ntitle: x\n---\n# Body\n');self.assertEqual((front,body.strip()),('title: x','# Body'))
    def test_inline_escapes_html_and_styles(self):
        html=markdown.inline('a <b> **bold** `x<y` [l](http://e.x) _i_',INK)
        self.assertIn('&lt;b&gt;',html);self.assertIn('<b>bold</b>',html);self.assertIn('x&lt;y',html)
        self.assertIn('href="http://e.x"',html);self.assertIn('<i>i</i>',html);self.assertNotIn('<script',markdown.inline('<script>',INK))


class HighlightTests(unittest.TestCase):
    def test_python_tokens_and_multiline_string(self):
        spans,state=tokenize('def f(x): return "a" # c','python')
        self.assertEqual([kind for _s,_e,kind in spans],['keyword','function','keyword','string','comment']);self.assertIsNone(state)
        spans,state=tokenize('x = """open','python');self.assertEqual(state,('string','"""'))
        spans,state=tokenize('still inside','python',state);self.assertEqual((spans,state),([(0,12,'string')],('string','"""')))
        spans,state=tokenize('end""" + 1','python',state);self.assertIsNone(state);self.assertEqual(spans[-1][2],'number')
    def test_json_keys_and_shell_variables(self):
        kinds=[k for _s,_e,k in tokenize('{"name": "wysun", "n": 3}','json')[0]];self.assertEqual(kinds,['key','string','key','number'])
        self.assertIn('constant',[k for _s,_e,k in tokenize('echo "$HOME" $PATH','shell')[0]])
    def test_language_lookup(self):
        self.assertEqual(language_for_path('/x/a.PY'),'python');self.assertEqual(language_for_fence('bash'),'shell')
        self.assertEqual(language_for_fence(''),'plain');self.assertEqual(language_for_path('a.unknown'),'plain')
    def test_block_comment_state_carries_over(self):
        _spans,state=tokenize('int a; /* open','clike');self.assertEqual(state,('comment','*/'))
        spans,state=tokenize('close */ int b;','clike',state);self.assertIsNone(state);self.assertEqual(spans[0],(0,8,'comment'))


if __name__=='__main__':unittest.main()
