
-- Fix: use modular arithmetic to avoid integer overflow
CREATE OR REPLACE FUNCTION hash_embed_384(text_input TEXT)
RETURNS vector(384) AS $$
DECLARE
  tokens TEXT[];
  vec FLOAT8[] := ARRAY(SELECT 0.0 FROM generate_series(1, 384));
  h BIGINT;
  h2 BIGINT;
  idx INT;
  idx2 INT;
  norm FLOAT8 := 0.0;
  token TEXT;
  i INT;
BEGIN
  tokens := regexp_split_to_array(lower(text_input), '\s+');
  FOREACH token IN ARRAY tokens LOOP
    IF token = '' THEN CONTINUE; END IF;
    h := 0;
    FOR i IN 1..length(token) LOOP
      h := ((h * 32) - h + ascii(substr(token, i, 1))) % 2147483647;
    END LOOP;
    idx := abs(h % 384)::int + 1;
    vec[idx] := vec[idx] + 1.0;

    h2 := 0;
    FOR i IN 1..length(token) LOOP
      h2 := ((h2 * 128) - h2 + ascii(substr(token, i, 1))) % 2147483647;
    END LOOP;
    idx2 := abs(h2 % 384)::int + 1;
    vec[idx2] := vec[idx2] + 0.5;
  END LOOP;

  FOR i IN 1..384 LOOP
    norm := norm + vec[i] * vec[i];
  END LOOP;
  norm := sqrt(norm);
  IF norm > 0 THEN
    FOR i IN 1..384 LOOP
      vec[i] := vec[i] / norm;
    END LOOP;
  END IF;

  RETURN vec::vector(384);
END;
$$ LANGUAGE plpgsql IMMUTABLE;
