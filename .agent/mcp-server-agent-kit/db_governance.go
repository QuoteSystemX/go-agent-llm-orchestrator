package main

import "encoding/json"

func (d *DB) SaveProposal(p *CouncilProposal) error {
	voters := p.Voters
	if voters == nil {
		voters = []string{}
	}
	votersJSON, err := json.Marshal(voters)
	if err != nil {
		return err
	}

	_, err = d.conn.Exec(
		`INSERT INTO proposals (id, title, proposer, votes, voters, required, status, created_at, command_type, command_data)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		 ON CONFLICT (id) DO UPDATE SET
		   title=EXCLUDED.title, proposer=EXCLUDED.proposer,
		   votes=EXCLUDED.votes, voters=EXCLUDED.voters, required=EXCLUDED.required,
		   status=EXCLUDED.status, created_at=EXCLUDED.created_at,
		   command_type=EXCLUDED.command_type, command_data=EXCLUDED.command_data`,
		p.ID, p.Title, p.Proposer, p.Votes, string(votersJSON), p.Required, p.Status, p.CreatedAt, p.CommandType, p.CommandData,
	)
	return err
}

func (d *DB) GetProposals() ([]*CouncilProposal, error) {
	rows, err := d.conn.Query("SELECT id, title, proposer, votes, voters, required, status, created_at, command_type, command_data FROM proposals")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var ps []*CouncilProposal
	for rows.Next() {
		p := &CouncilProposal{}
		var votersJSON *string
		if err := rows.Scan(&p.ID, &p.Title, &p.Proposer, &p.Votes, &votersJSON, &p.Required, &p.Status, &p.CreatedAt, &p.CommandType, &p.CommandData); err != nil {
			return nil, err
		}
		if votersJSON != nil && *votersJSON != "" {
			// Legacy rows written before the voters column existed may contain
			// NULL; tolerate that as "no recorded voters" rather than failing.
			if err := json.Unmarshal([]byte(*votersJSON), &p.Voters); err != nil {
				p.Voters = []string{}
			}
		}
		ps = append(ps, p)
	}
	return ps, nil
}
