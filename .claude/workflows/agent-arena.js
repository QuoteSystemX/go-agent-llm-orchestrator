export const meta = {
  name: 'agent-arena',
  description: 'N-candidate independent-per-round debate over a role/subtask, judged (Claude-native port of orchestration/agent_arena.py)',
  phases: [
    { title: 'Debate', detail: 'Each candidate argues, blind to the others, across rounds' },
    { title: 'Judge', detail: 'Pick the winning candidate' },
  ],
}

// Claude-subagent variant of agent_arena.py's conduct_debate(). "Candidates" are competing
// approaches/names (not necessarily distinct agent personas) arguing for a role/subtask across
// NUM_ROUNDS rounds — each candidate sees only its OWN prior-round argument, never another
// candidate's, which is what makes this a genuine debate rather than a shared-context discussion.
// See tasks/done/.../port-agent-arena-*.md for the design record.

const NUM_ROUNDS = 2

const subtask = args && args.subtask
const role = (args && args.role) || 'debate'
const candidates = args && args.candidates

if (!subtask || !Array.isArray(candidates) || candidates.length < 2) {
  throw new Error(
    'agent-arena requires args.subtask (string) and args.candidates (array of 2+ candidate names). ' +
    'Optional: args.role (label for what is being decided).'
  )
}

const ARGUMENT_SCHEMA = {
  type: 'object',
  properties: { argument: { type: 'string' } },
  required: ['argument'],
}

const JUDGE_SCHEMA = {
  type: 'object',
  properties: {
    winner: { type: 'string', enum: candidates },
    reasoning: { type: 'string' },
  },
  required: ['winner', 'reasoning'],
}

phase('Debate')
// rounds[i] = { round: i+1, arguments: { candidateName: text } }
const rounds = []
for (let i = 0; i < NUM_ROUNDS; i++) {
  const roundNum = i + 1

  const argResults = await parallel(
    candidates.map((candidate) => async () => {
      // Only this candidate's OWN prior rounds — never another candidate's argument.
      const ownPrior = rounds
        .map((r) => (r.arguments[candidate] ? `Round ${r.round}: ${r.arguments[candidate]}` : null))
        .filter(Boolean)
        .join('\n')
      const prompt =
        `You are agent '${candidate}' arguing in a structured debate.\n` +
        `Role being filled: ${role}\n` +
        `Subtask to solve: ${subtask}\n` +
        (ownPrior ? `Your prior argument(s):\n${ownPrior}\n` : '') +
        `Round ${roundNum}: Argue clearly and concisely (3-5 sentences) why your approach is the ` +
        `best choice for this subtask. You have NOT seen any other candidate's argument.`
      const result = await agent(prompt, { label: `${candidate}-r${roundNum}`, phase: 'Debate', schema: ARGUMENT_SCHEMA })
      return { candidate, argument: result ? result.argument : null }
    })
  )

  const argumentsByCandidate = {}
  for (const r of argResults) {
    if (r) argumentsByCandidate[r.candidate] = r.argument || ''
  }
  rounds.push({ round: roundNum, arguments: argumentsByCandidate })
  log(`Round ${roundNum} complete: ${candidates.length} candidate(s) argued independently`)
}

phase('Judge')
let debateText = ''
for (const r of rounds) {
  debateText += `\n--- Round ${r.round} ---\n`
  for (const c of candidates) {
    debateText += `${c}: ${r.arguments[c] || '(no argument)'}\n`
  }
}
const judgePrompt =
  `You are the judge for a structured agent debate.\n` +
  `Role: ${role}\nSubtask: ${subtask}\nCandidates: ${candidates.join(', ')}\n\n` +
  `Debate transcript:\n${debateText}\n\n` +
  `Pick the single best candidate for this role and subtask and explain why.`
const judgeResult = await agent(judgePrompt, { label: 'judge', schema: JUDGE_SCHEMA })

log(`Winner: ${judgeResult.winner}`)

return {
  role,
  subtask,
  candidates,
  rounds,
  winner: judgeResult.winner,
  reasoning: judgeResult.reasoning,
}
