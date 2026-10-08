import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import unittest
from scripts.rewrite_npm import rewrite_command_line, process_hook_payload


class TestRewriteNpm(unittest.TestCase):
    def test_single_commands(self):
        cases = [
            ("npm i express", "pnpm add express"),
            ("npm install express lodash", "pnpm add express lodash"),
            ("npm i -D typescript @types/node", "pnpm add -D typescript @types/node"),
            ("npm install --save-dev vitest", "pnpm add --save-dev vitest"),
            ("npm i -g pnpm", "pnpm add -g pnpm"),
            ("npm i -E react", "pnpm add -E react"),
            ("npm i -O optional-pkg", "pnpm add -O optional-pkg"),
            ("npm i --save-peer peer-pkg", "pnpm add --save-peer peer-pkg"),
            ("npm install", "pnpm install"),
            ("npm i", "pnpm install"),
            ("npm ci", "pnpm install --frozen-lockfile"),
            ("npm uninstall lodash", "pnpm remove lodash"),
            ("npm rm lodash", "pnpm remove lodash"),
            ("npm remove lodash", "pnpm remove lodash"),
            ("npm update", "pnpm update"),
            ("npm up", "pnpm update"),
            ("npm prune", "pnpm prune"),
            ("npm run build", "pnpm run build"),
            ("npm run test -- --watch", "pnpm run test -- --watch"),
            ("npm test", "pnpm test"),
            ("npm t", "pnpm test"),
            ("npm start", "pnpm start"),
            ("npm stop", "pnpm stop"),
            ("npm restart", "pnpm restart"),
            ("npx rimraf dist", "pnpm dlx rimraf dist"),
            ("npm exec prettier -- .", "pnpm dlx prettier -- ."),
            ("npm create vite@latest my-app", "pnpm create vite@latest my-app"),
            ("npm init vite@latest", "pnpm create vite@latest"),
            ("npm init", "pnpm init"),
            ("npm init -y", "pnpm init"),
            ("npm ls", "pnpm ls"),
            ("npm list", "pnpm ls"),
            ("npm why chalk", "pnpm why chalk"),
            ("npm explain chalk", "pnpm why chalk"),
            ("npm outdated", "pnpm outdated"),
            ("npm audit", "pnpm audit"),
            ("npm audit fix", "pnpm audit --fix"),
            ("npm cache clean --force", "pnpm store prune"),
            ("npm link", "pnpm link"),
            ("npm unlink", "pnpm unlink"),
            ("npm pack", "pnpm pack"),
            ("npm publish", "pnpm publish"),
            ("npm rebuild", "pnpm rebuild"),
        ]
        for original, expected in cases:
            with self.subTest(cmd=original):
                rewritten, changed = rewrite_command_line(original)
                self.assertTrue(changed, f"Expected {original} to be marked changed")
                self.assertEqual(rewritten, expected)

    def test_environment_variables(self):
        original = "NODE_ENV=production PORT=8080 npm start"
        expected = "NODE_ENV=production PORT=8080 pnpm start"
        rewritten, changed = rewrite_command_line(original)
        self.assertTrue(changed)
        self.assertEqual(rewritten, expected)

    def test_compound_commands(self):
        original = "cd frontend && npm install && npm run build"
        expected = "cd frontend && pnpm install && pnpm run build"
        rewritten, changed = rewrite_command_line(original)
        self.assertTrue(changed)
        self.assertEqual(rewritten, expected)

        original2 = "npm test || npm run fallback"
        expected2 = "pnpm test || pnpm run fallback"
        rewritten2, changed2 = rewrite_command_line(original2)
        self.assertTrue(changed2)
        self.assertEqual(rewritten2, expected2)

        original3 = "npm i; npm run lint"
        expected3 = "pnpm install; pnpm run lint"
        rewritten3, changed3 = rewrite_command_line(original3)
        self.assertTrue(changed3)
        self.assertEqual(rewritten3, expected3)

    def test_rest_of_command_preserved_verbatim(self):
        cases = [
            ("npm test 2>&1 | tee log", "pnpm test 2>&1 | tee log"),
            ("npm run build > out.log", "pnpm run build > out.log"),
            ("npm start &>log", "pnpm start &>log"),
            ('npm i foo && echo "a   b"', 'pnpm add foo && echo "a   b"'),
            ("npm install --prefix $HOME/app", "pnpm install --prefix $HOME/app"),
            ("npm i --prefix ./x lodash", "pnpm add --prefix ./x lodash"),
            ("cd app\nnpm i foo", "cd app\npnpm add foo"),
            ("npm install\nnpm test", "pnpm install\npnpm test"),
            ("FOO=a\\ b npm i x", "FOO=a\\ b pnpm add x"),
            ("npx eslint src/*.js", "pnpm dlx eslint src/*.js"),
            ('FOO="a b" npm ci', 'FOO="a b" pnpm install --frozen-lockfile'),
            ("npm run dev & npm test", "pnpm run dev & pnpm test"),
        ]
        for original, expected in cases:
            with self.subTest(cmd=original):
                self.assertEqual(rewrite_command_line(original), (expected, True))

    def test_negative_cases_no_rewrite(self):
        negatives = [
            'git commit -m "fix: updated npm install issue"',
            'echo "you should run npm install"',
            'cat README.md | grep npm',
            'node scripts/npm-checker.js',
            'pnpm add express',
            'python3 -c "print(1)"',
            'ls -la',
        ]
        for cmd in negatives:
            with self.subTest(cmd=cmd):
                rewritten, changed = rewrite_command_line(cmd)
                self.assertFalse(changed, f"Command should not be changed: {cmd}")
                self.assertEqual(rewritten, cmd)

    def test_hook_payload_processing(self):
        payload = {
            "toolCall": {
                "name": "run_command",
                "args": {
                    "CommandLine": "npm install chalk"
                }
            }
        }
        res = process_hook_payload(payload)
        self.assertEqual(res["decision"], "allow")
        self.assertIn("overwrite", res)
        self.assertEqual(res["overwrite"]["CommandLine"], "pnpm add chalk")
        self.assertIn("always-pnpm", res["reason"])

        # Non-rewritten payload
        payload_noop = {
            "toolCall": {
                "name": "run_command",
                "args": {
                    "CommandLine": "ls -la"
                }
            }
        }
        res_noop = process_hook_payload(payload_noop)
        self.assertEqual(res_noop, {"decision": "allow"})


if __name__ == "__main__":
    unittest.main()
