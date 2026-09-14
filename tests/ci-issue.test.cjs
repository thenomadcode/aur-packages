const { test } = require('node:test');
const assert = require('node:assert/strict');
const syncIssue = require('../.github/scripts/sync-ci-issue.cjs');

function fixture(open) {
  const requests = [];
  const github = {
    paginate: async () => open,
    rest: { issues: {
      listForRepo: () => {},
      create: async (args) => requests.push(['create', args]),
      update: async (args) => requests.push(['update', args]),
      createComment: async (args) => requests.push(['comment', args]),
    } },
  };
  const args = { github, context: { repo: { owner: 'owner', repo: 'repo' } },
    title: 'package: build failed', labels: ['ci-failure', 'package'],
    body: 'Failure details', recovery: 'Verified successful build' };
  return { requests, args };
}
const issue = (number, extra = {}) => ({ number, title: 'package: build failed',
  user: { login: 'github-actions[bot]' }, ...extra });

test('repeated failure does not create duplicate issues', async () => {
  const { requests, args } = fixture([issue(12)]);
  await syncIssue({ ...args, failed: true });
  assert.deepEqual(requests, []);
});

test('first failure opens one issue with the supplied evidence', async () => {
  const { requests, args } = fixture([]);
  await syncIssue({ ...args, failed: true });
  assert.deepEqual(requests, [['create', { ...args.context.repo,
    title: args.title, labels: args.labels, body: args.body }]]);
});

test('recovery closes all matching bot reports but leaves human issues and PRs', async () => {
  const { requests, args } = fixture([issue(12), issue(14),
    issue(15, { user: { login: 'maintainer' } }), issue(16, { title: 'other failure' }),
    issue(17, { pull_request: {} })]);
  await syncIssue({ ...args, failed: false });
  assert.deepEqual(requests.filter(([kind]) => kind === 'update').map(([, args]) => args), [
    { ...args.context.repo, issue_number: 12, state: 'closed', state_reason: 'completed' },
    { ...args.context.repo, issue_number: 14, state: 'closed', state_reason: 'completed' },
  ]);
  assert.equal(requests.filter(([kind]) => kind === 'comment').length, 2);
});
