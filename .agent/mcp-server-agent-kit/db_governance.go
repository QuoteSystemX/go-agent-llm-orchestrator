package main

func (d *DB) SaveProposal(p *CouncilProposal) error {
	_, err := d.conn.Exec(
		"INSERT OR REPLACE INTO proposals (id, title, proposer, votes, required, status, created_at, command_type, command_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
