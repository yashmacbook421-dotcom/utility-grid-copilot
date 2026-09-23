
-- Create a function that inserts a document and its chunks from a JSON array
CREATE OR REPLACE FUNCTION insert_doc_with_chunks(
  p_title TEXT,
  p_organization TEXT,
  p_document_type TEXT,
  p_source_url TEXT,
  p_chunks TEXT[]
)
RETURNS uuid AS $$
DECLARE
  doc_id uuid;
  chunk_text_val TEXT;
  idx INT := 0;
BEGIN
  INSERT INTO documents (title, organization, document_type, source_url)
  VALUES (p_title, p_organization, p_document_type, p_source_url)
  RETURNING id INTO doc_id;

  FOREACH chunk_text_val IN ARRAY p_chunks LOOP
    INSERT INTO document_chunks (document_id, chunk_index, content, embedding)
    VALUES (doc_id, idx, chunk_text_val, hash_embed_384(chunk_text_val));
    idx := idx + 1;
  END LOOP;

  RETURN doc_id;
END;
$$ LANGUAGE plpgsql;
