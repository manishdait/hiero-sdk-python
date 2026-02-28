const LINKBOT_MISSING_ISSUE_MARKER = '<!-- LinkBot Missing Issue -->';
const LINKBOT_UNASSIGNED_ISSUE_MARKER = '<!-- LinkBot Unassigned Linked Issue -->';

const requireAuthorAssigned = (process.env.REQUIRE_AUTHOR_ASSIGNED || 'true').toLowerCase() === 'true';

async function getLinkedOpenIssues(github, owner, repo, prNumber) {
  const query = `
    query($owner: String!, $repo: String!, $prNumber: Int!) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $prNumber) {
          closingIssuesReferences(first: 100) {
            nodes {
              number
              state
              assignees(first: 100) {
                nodes {
                  login
                }
              }
            }
          }
        }
      }
    }
  `;

  try {
    const result = await github.graphql(query, { owner, repo, prNumber });
    const issues = result.repository.pullRequest.closingIssuesReferences.nodes || [];
    return issues.filter(issue => issue.state === 'OPEN');
  } catch (error) {
    console.error(`Failed to fetch linked issues for PR #${prNumber}:`, error.message);
    return null;
  }
}

function isAuthorAssignedToAnyIssue(issues, authorLogin) {
  return issues.some(issue =>
    (issue.assignees?.nodes || []).some(assignee => assignee.login === authorLogin)
  );
}

module.exports = async ({ github, context }) => {
  let prNumber;
  try {
    const isDryRun = process.env.DRY_RUN === 'true';
    prNumber = Number(process.env.PR_NUMBER) || context.payload.pull_request?.number;

    if (!prNumber) {
      throw new Error('PR number could not be determined');
    }

    console.log(`Processing PR #${prNumber} (Dry run: ${isDryRun})`);

    // For workflow_dispatch, we need to fetch PR details
    let prData;
    if (context.payload.pull_request) {
      prData = context.payload.pull_request;
    } else {
      // workflow_dispatch case - fetch PR data
      const prResponse = await github.rest.pulls.get({
        owner: context.repo.owner,
        repo: context.repo.repo,
        pull_number: prNumber,
      });
      prData = prResponse.data;
    }

    const authorType = prData.user?.type;
    const authorLogin = prData.user?.login;

    if (authorType === "Bot" || authorLogin?.endsWith('[bot]')) {
      console.log(`Skipping comment: PR created by bot (${authorLogin})`);
      return;
    }

    const comments = await github.rest.issues.listComments({
      owner: context.repo.owner,
      repo: context.repo.repo,
      issue_number: prNumber,
    });

    const alreadyCommentedMissingIssue = comments.data.some(comment =>
      comment.body?.includes(LINKBOT_MISSING_ISSUE_MARKER)
    );

    const alreadyCommentedUnassignedIssue = comments.data.some(comment =>
      comment.body?.includes(LINKBOT_UNASSIGNED_ISSUE_MARKER)
    );

    const linkedIssues = await getLinkedOpenIssues(github, context.repo.owner, context.repo.repo, prNumber);
    if (linkedIssues === null) {
      console.log('Could not determine linked issues. Skipping comment for safety.');
      return;
    }

    if (linkedIssues.length === 0) {
      if (alreadyCommentedMissingIssue) {
        console.log('LinkBot missing-issue reminder already posted on this PR');
        return;
      }

      const safeAuthor = authorLogin ?? 'there';
      const commentBody = [`${LINKBOT_MISSING_ISSUE_MARKER}` +
        `Hi @${safeAuthor}, this is **LinkBot** 👋`,
        ``,
        `Linking pull requests to issues helps us significantly with reviewing pull requests and keeping the repository healthy.`,
        ``,
        `🚨 **This pull request does not have an issue linked.**`,
        `If this PR remains unlinked, it will be automatically closed.`,
        ``,
        `Please link an issue using the following format:`,
        '```',
        'Fixes #123',
        '```',
        ``,
        `📖 Guide:`,
      `[docs/sdk_developers/how_to_link_issues.md](https://github.com/${context.repo.owner}/${context.repo.repo}/blob/main/docs/sdk_developers/how_to_link_issues.md)`,
        ``,
        `If no issue exists yet, please create one:`,
      `[docs/sdk_developers/creating_issues.md](https://github.com/${context.repo.owner}/${context.repo.repo}/blob/main/docs/sdk_developers/creating_issues.md)`,
        ``,
        `Thanks!`
      ].join('\n');

      if (isDryRun) {
        console.log('DRY RUN: Would post the following comment:');
        console.log('---');
        console.log(commentBody);
        console.log('---');
      } else {
        await github.rest.issues.createComment({
          owner: context.repo.owner,
          repo: context.repo.repo,
          issue_number: prNumber,
          body: commentBody,
        });
        console.log('LinkBot comment posted successfully');
      }
    } else if (requireAuthorAssigned && !isAuthorAssignedToAnyIssue(linkedIssues, authorLogin)) {
      if (alreadyCommentedUnassignedIssue) {
        console.log('LinkBot unassigned-issue reminder already posted on this PR');
        return;
      }

      const safeAuthor = authorLogin ?? 'there';
      const linkedIssueList = linkedIssues.map(issue => `#${issue.number}`).join(', ');
      const commentBody = [`${LINKBOT_UNASSIGNED_ISSUE_MARKER}` +
        `Hi @${safeAuthor}, this is **LinkBot** 👋`,
        ``,
        `🚨 **This pull request is linked to issue(s), but you are not assigned to any of them.**`,
        `If this remains unchanged, this pull request will be automatically closed.`,
        ``,
        `Linked issue(s): ${linkedIssueList}`,
        ``,
        `Please get assigned to one of the linked issues and keep the link in this PR description.`,
        `For Good First Issues, comment \`/assign\` on the issue.`,
        ``,
        `📖 Guide:`,
        `[docs/sdk_developers/how_to_link_issues.md](https://github.com/${context.repo.owner}/${context.repo.repo}/blob/main/docs/sdk_developers/how_to_link_issues.md)`,
        ``,
        `Thanks!`
      ].join('\n');

      if (isDryRun) {
        console.log('DRY RUN: Would post the following unassigned-issue comment:');
        console.log('---');
        console.log(commentBody);
        console.log('---');
      } else {
        await github.rest.issues.createComment({
          owner: context.repo.owner,
          repo: context.repo.repo,
          issue_number: prNumber,
          body: commentBody,
        });
        console.log('LinkBot unassigned-issue comment posted successfully');
      }
    } else {
      console.log('PR has valid linked issue assignment - no comment needed');
    }
  } catch (error) {
    console.error('Error processing PR:', error);
    console.error('PR number:', prNumber);
    console.error('Repository:', `${context.repo.owner}/${context.repo.repo}`);
    throw error;
  }
};