package main

func (d *DB) SaveProposal(p *CouncilProposal) error {
	_, err := d.conn.Exec(
		`INSERT INTO proposals (id, title, proposer, votes, required, status, created_at, command_type, command_data)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		 ON CONFLICT (id) DO UPDATE SET
		   title=EXCLUDED.title, proposer=EXCLUDED.proposer,
		   votes=EXCLUDED.votes, required=EXCLUDED.required,
		   status=EXCLUDED.status, created_at=EXCLUDED.created_at,
		   command_type=EXCLUDED.command_type, command_data=EXCLUDED.command_data`,
		p.ID, p.Title, p.Proposer, p.Votes, p.Required, p.Status, p.CreatedAt, p.CommandType, p.CommandData,
	)
	return err
}

func (d *DB) GetProposals() ([]*CouncilProposal, error) {
	rows, err := d.conn.Query("SELECT id, title, proposer, votes, required, status, created_at, command_type, command_data FROM proposals")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var ps []*CouncilProposal
	for rows.Next() {
		p := &CouncilProposal{}
		if err := rows.Scan(&p.ID, &p.Title, &p.Proposer, &p.Votes, &p.Required, &p.Status, &p.CreatedAt, &p.CommandType, &p.CommandData); err != nil {
			return nil, err
		}
		ps = append(ps, p)
	}
	return ps, nil
}
