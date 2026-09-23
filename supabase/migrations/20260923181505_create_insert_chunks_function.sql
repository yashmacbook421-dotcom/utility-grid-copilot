
-- Create a function to insert chunks for an existing document
CREATE OR REPLACE FUNCTION insert_chunks_for_doc(
  p_doc_id uuid,
  p_chunks TEXT[]
)
RETURNS void AS $$
DECLARE
  chunk_text_val TEXT;
  idx INT := 0;
BEGIN
  FOREACH chunk_text_val IN ARRAY p_chunks LOOP
    INSERT INTO document_chunks (document_id, chunk_index, content, embedding)
    VALUES (p_doc_id, idx, chunk_text_val, hash_embed_384(chunk_text_val));
    idx := idx + 1;
  END LOOP;
END;
$$ LANGUAGE plpgsql;
