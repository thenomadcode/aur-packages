// Reconcile only reports created by this automation; never close human issues.
module.exports = async function syncIssue({ github, context, title, labels, failed, body, recovery }) {
  const open = await github.paginate(github.rest.issues.listForRepo, {
    ...context.repo, state: 'open', labels: labels.join(','), per_page: 100,
  });
  const matching = open.filter(issue => !issue.pull_request && issue.title === title &&
    issue.user?.login === 'github-actions[bot]');
  if (failed) {
    if (matching.length === 0) {
      await github.rest.issues.create({ ...context.repo, title, labels, body });
    }
    return;
  }
  for (const issue of matching) {
    await github.rest.issues.createComment({ ...context.repo, issue_number: issue.number, body: recovery });
    await github.rest.issues.update({
      ...context.repo, issue_number: issue.number, state: 'closed', state_reason: 'completed',
    });
  }
};
