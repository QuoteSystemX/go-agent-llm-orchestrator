package main

import (
	"database/sql"
	"fmt"
	"time"
)

func (d *DB) SaveVeto(v *VetoRecord) error {
	_, err := d.conn.Exec(
		`INSERT INTO veto_records (id, plan_or_task_ref, status, created_by, lifted_by, reason, proposal_id, created_at, lifted_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		 ON CONFLICT (id) DO UPDATE SET
		   plan_or_task_ref=EXCLUDED.plan_or_task_ref, status=EXCLUDED.status,
		   created_by=EXCLUDED.created_by, lifted_by=EXCLUDED.lifted_by, reason=EXCLUDED.reason,
		   proposal_id=EXCLUDED.proposal_id, created_at=EXCLUDED.created_at, lifted_at=EXCLUDED.lifted_at`,
		v.ID, v.PlanOrTaskRef, v.Status, v.CreatedBy, v.LiftedBy, v.Reason, v.ProposalID, v.CreatedAt, v.LiftedAt,
	)
	return err
}

func (d *DB) GetVeto(id string) (*VetoRecord, error) {
	v := &VetoRecord{}
	var liftedBy, reason sql.NullString
	err := d.conn.QueryRow(
		"SELECT id, plan_or_task_ref, status, created_by, lifted_by, reason, proposal_id, created_at, lifted_at FROM veto_records WHERE id = $1",
		id,
	).Scan(&v.ID, &v.PlanOrTaskRef, &v.Status, &v.CreatedBy, &liftedBy, &reason, &v.ProposalID, &v.CreatedAt, &v.LiftedAt)
	if err != nil {
		return nil, err
	}
	v.LiftedBy = liftedBy.String
	v.Reason = reason.String
	return v, nil
}

// LiftVeto flips a veto's status to "lifted" — a single conditional UPDATE is already atomic in
// Postgres (no need for an explicit transaction for one statement). Returns an explicit error if
// the veto doesn't exist or was already lifted, rather than silently no-op'ing, so a caller (or a
// racing second lift attempt) gets an unambiguous signal instead of a false "success".
func (d *DB) LiftVeto(id, liftedBy string) error {
	res, err := d.conn.Exec(
		`UPDATE veto_records SET status='lifted', lifted_by=$1, lifted_at=$2 WHERE id=$3 AND status='active'`,
		liftedBy, time.Now(), id,
	)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return fmt.Errorf("veto %s not found or already lifted", id)
	}
	return nil
}
