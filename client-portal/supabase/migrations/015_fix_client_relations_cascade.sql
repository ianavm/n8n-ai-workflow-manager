-- Migration 015: Add ON DELETE CASCADE to client_id FKs
-- Prevents orphaned records in client_health_scores, client_interactions, renewal_pipeline
-- when a client is deleted from the clients table.

ALTER TABLE client_health_scores
  DROP CONSTRAINT client_health_scores_client_id_fkey,
  ADD CONSTRAINT client_health_scores_client_id_fkey
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE;

ALTER TABLE client_interactions
  DROP CONSTRAINT client_interactions_client_id_fkey,
  ADD CONSTRAINT client_interactions_client_id_fkey
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE;

ALTER TABLE renewal_pipeline
  DROP CONSTRAINT renewal_pipeline_client_id_fkey,
  ADD CONSTRAINT renewal_pipeline_client_id_fkey
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE;
