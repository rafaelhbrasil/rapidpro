# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-10-18 19:32
from __future__ import unicode_literals

from django.db import migrations

SQL = """
CREATE OR REPLACE FUNCTION public.temba_insert_flowcategorycount(_flow_id integer, result_key text, _result json, _count integer)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
  BEGIN
    INSERT INTO flows_flowcategorycount("flow_id", "node_uuid", "result_key", "result_name", "category_name", "count", "is_squashed")
      VALUES(_flow_id, (_result->>'node_uuid')::uuid, result_key, _result->>'name', _result->>'category', _count, FALSE);
  END;
$function$;

CREATE OR REPLACE FUNCTION public.temba_update_category_counts(_flow_id integer, new json, old json)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
DECLARE
  DECLARE node_uuid text;
  DECLARE result_key text;
  DECLARE result_value text;
  DECLARE value_key text;
  DECLARE value_value text;
  DECLARE _new json;
  DECLARE _old json;
BEGIN
    -- look over the keys in our new results
    FOR result_key, result_value IN SELECT key, value from json_each(new)
    LOOP
        -- if its a new key, create a new count
        IF (old->result_key) IS NULL THEN
            execute temba_insert_flowcategorycount(_flow_id, result_key, new->result_key, 1);
        ELSE
            _new := new->result_key;
            _old := old->result_key;

            IF (_old->>'node_uuid') = (_new->>'node_uuid') THEN
                -- we already have this key, check if the value is newer
                IF timestamptz(_new->>'modified_on') > timestamptz(_old->>'modified_on') THEN
                    -- found an update to an existing key, create a negative and positive count accordingly
                    execute temba_insert_flowcategorycount(_flow_id, result_key, _old, -1);
                    execute temba_insert_flowcategorycount(_flow_id, result_key, _new, 1);
                END IF;
            ELSE
                -- the parent has changed, out with the old in with the new
                execute temba_insert_flowcategorycount(_flow_id, result_key, _old, -1);
                execute temba_insert_flowcategorycount(_flow_id, result_key, _new, 1);
            END IF;
        END IF;
    END LOOP;

    -- look over keys in our old results that might now be gone
    FOR result_key, result_value IN SELECT key, value from json_each(old)
    LOOP
        IF (new->result_key) IS NULL THEN
            -- found a key that's since been deleted, add a negation
            execute temba_insert_flowcategorycount(_flow_id, result_key, old->result_key, -1);
        END IF;
    END LOOP;
END;
$function$;

CREATE OR REPLACE FUNCTION public.temba_update_flowcategorycount()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN

  IF TG_OP = 'DELETE' THEN

    -- ignore test contacts
    IF temba_contact_is_test(OLD.contact_id) THEN RETURN NULL; END IF;

    execute temba_update_category_counts(OLD.flow_id, NULL, OLD.results::json);

    RETURN NULL;
  END IF;

  -- ignore test contacts
  IF temba_contact_is_test(NEW.contact_id) THEN RETURN NULL; END IF;

  -- FlowRun being updated
  IF TG_OP = 'INSERT' THEN
    execute temba_update_category_counts(NEW.flow_id, NEW.results::json, NULL);
  ELSIF TG_OP = 'UPDATE' THEN
    execute temba_update_category_counts(NEW.flow_id, NEW.results::json, OLD.results::json);
  ELSE
    SELECT TG_OP;
  END IF;

  RETURN NULL;
END;
$function$;


CREATE TRIGGER temba_flowrun_update_flowcategorycount
   AFTER INSERT OR DELETE OR UPDATE OF results
   ON flows_flowrun
   FOR EACH ROW
   EXECUTE PROCEDURE temba_update_flowcategorycount();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0116_flowcategorycount'),
    ]

    operations = [
        migrations.RunSQL(SQL),
    ]
