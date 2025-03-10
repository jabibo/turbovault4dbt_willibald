import codecs
from datetime import datetime
import os
import procs.sqlite3.helper as helper

# Changes: JB: added edts
# todo: HKE as Replacement from HK fixed
def gen_hashed_columns(cursor,source, hashdiff_naming):
  
  command = ""

  source_name, source_object = helper.source_split(source)

  query = f"""
              SELECT  Target_Primary_Key_Physical_Name
                    , GROUP_CONCAT(Source_Column_Physical_Name)
                    , IS_SATELLITE 
                    , effective_date_type
                    , effective_date_attribute
              FROM 
              (
                SELECT DISTINCT
                    h.Target_Primary_Key_Physical_Name
                  , h.Source_Column_Physical_Name
                  , FALSE as IS_SATELLITE
                  , src.effective_date_type
                  , src.effective_date_attribute
                FROM hub_entities h
                inner join source_data src 
                  on h.Source_Table_Identifier = src.Source_table_identifier
                WHERE src.Source_System = '{source_name}' 
                and src.Source_Object = '{source_object}'
                and not coalesce(is_ref_object, false)
                ORDER BY h.Target_Column_Sort_Order
              ) 
              GROUP BY Target_Primary_Key_Physical_Name
              UNION ALL
              SELECT  Target_Primary_Key_Physical_Name
                    , GROUP_CONCAT(Source_Column_Physical_Name)
                    , IS_SATELLITE 
                    , effective_date_type
                    , effective_date_attribute
              FROM
              (
                SELECT  l.Target_Primary_Key_Physical_Name
                      , l.Source_Column_Physical_Name
                      , FALSE as IS_SATELLITE
                      , src.effective_date_type
                      , src.effective_date_attribute
                FROM link_entities l
                inner join source_data src
                  on l.Source_Table_Identifier = src.Source_table_identifier
                WHERE src.Source_System = '{source_name}' 
                and src.Source_Object = '{source_object}'
                ORDER BY l.Target_Column_Sort_Order
              )
              group by Target_Primary_Key_Physical_Name
              UNION ALL
              SELECT  link_primary_key_physical_name
                    , GROUP_CONCAT(Source_Column_Physical_Name)
                    , IS_SATELLITE 
                    , effective_date_type
                    , effective_date_attribute
              FROM
              (
                SELECT  l.link_primary_key_physical_name
                        , l.Source_Column_Physical_Name
                        , FALSE as IS_SATELLITE
                        , src.effective_date_type
                        , src.effective_date_attribute
                FROM nh_link_entities l
                inner join source_data src 
                  on l.Source_Table_Identifier = src.Source_table_identifier
                WHERE l.identifying = True 
                  and src.Source_System = '{source_name}' 
                  and src.Source_Object = '{source_object}'
                ORDER BY l.Target_Column_Sort_Order
              )
              group by link_primary_key_physical_name              
              UNION ALL
              SELECT  Target_Satellite_Table_Physical_Name
                    , GROUP_CONCAT(Source_Column_Physical_Name)
                    , IS_SATELLITE 
                    , effective_date_type
                    , effective_date_attribute
              FROM 
              (
                SELECT DISTINCT  
                	    '{hashdiff_naming.replace("@@SatName", "")}' || s.Target_Satellite_Table_Physical_Name as Target_Satellite_Table_Physical_Name
                      , s.Source_Column_Physical_Name
                      , TRUE as IS_SATELLITE
                      , src.effective_date_type
                      , src.effective_date_attribute
                FROM hub_satellites s
                inner join source_data src 
                  on s.Source_Table_Identifier = src.Source_table_identifier
                WHERE src.Source_System = '{source_name}' 
                  and src.Source_Object = '{source_object}'
                  and not ma_attribute   
                order by s.Target_Column_Sort_Order
              )
              group by Target_Satellite_Table_Physical_Name
              UNION ALL
              SELECT  Target_Satellite_Table_Physical_Name
                    , GROUP_CONCAT(Source_Column_Physical_Name)
                    , IS_SATELLITE 
                    , effective_date_type
                    , effective_date_attribute
              FROM
              (
                SELECT  '{hashdiff_naming.replace("@@SatName", "")}' || s.Target_Satellite_Table_Physical_Name as Target_Satellite_Table_Physical_Name
                      , s.Source_Column_Physical_Name
                      , TRUE as IS_SATELLITE
                      , src.effective_date_type
                      , src.effective_date_attribute
              FROM link_satellites s
              inner join source_data src 
                on s.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' 
                and src.Source_Object = '{source_object}'
              order by s.Target_Column_Sort_Order)
              group by Target_Satellite_Table_Physical_Name
              """
  cursor.execute(query)
  results = cursor.fetchall()
  for hashkey in results:
  
    hashkey_name = hashkey[0]
    bk_list = hashkey[1].split(",")

    command = command + f"\t{hashkey_name}:\n"
    if hashkey[2]: 
      command = command + "\t\tis_hashdiff: true\n\t\tcolumns:\n"

      if hashkey[3]=='Type 1': 
        bk_list.append(hashkey[4])

      for bk in bk_list:
        command = command + f"\t\t\t- {bk}\n"  
    else:
      for bk in bk_list:
        command = command + f"\t\t- {bk}\n"
  
    if hashkey[3]=='Type 1' and not hashkey[2]: 
      hashkey_name = hashkey[0].replace('hk_', 'hke_')
      bk_list = (hashkey[1].split(","))
      bk_list.append(hashkey[4])
      command = command + f"\t{hashkey_name}:\n"
      for bk in bk_list:
          command = command + f"\t\t- {bk}\n"

  return command

def gen_multi_active_config(cursor,source):
  
  command = ""

  source_name, source_object = helper.source_split(source)

  query = f"""
              SELECT 
                  s.source_table_identifier
                  ,s.target_satellite_table_physical_name 
                  , s.hub_primary_key_physical_name 
                  , group_concat(s.target_column_physical_name) target_column_physical_name
              FROM hub_satellites s
              inner join source_data src 
                on s.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' 
                and src.Source_Object = '{source_object}'
                and  ma_attribute
              """
  cursor.execute(query)
  results = cursor.fetchall()
  # print(results)
  if not results:
    # print("not:",results)
    return ""
  command = ""

  for multi_active_config in results:
    if any(item is None for item in multi_active_config):
        continue    
    command += "multi_active_config:\n\t\tmulti_active_key:\n"    
    main_hashkey_column = multi_active_config[2]
    multi_active_key_list = multi_active_config[3].split(",")


    for multi_active_key in multi_active_key_list:
      command += f"\t\t\t- {multi_active_key}\n"  

    command +=  f"\t\tmain_hashkey_column: {main_hashkey_column}\n"
    
  # print(command)
  
  return command




def gen_derived_columns(cursor,source):
  
  command = ""

  source_name, source_object = helper.source_split(source)

  query = f"""
   SELECT 
              group_concat(source_column_physical_name), target_column_physical_name, transformation_rule  
              from
              (              
              SELECT 
              case when transformation_rule<>''
                     then transformation_rule
                     else source_column_physical_name end as source_column_physical_name 
              , target_column_physical_name
              , case when transformation_rule<>''
                     then True
                     else False end as transformation_rule
              FROM hub_satellites s
              inner join source_data src on s.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              and source_column_physical_name<>target_column_physical_name 
              union
              SELECT 
              source_column_physical_name 
              , target_column_physical_name  
              , False as transformation_rule              
              FROM link_satellites s
              inner join source_data src on s.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              and source_column_physical_name<>target_column_physical_name
              union
              SELECT distinct
              case when transformation_rule<>''
                     then transformation_rule
                     else source_column_physical_name end as source_column_physical_name
              , business_key_physical_name 
              , case when transformation_rule<>''
                     then True
                     else False end as transformation_rule
              FROM hub_entities s
              inner join source_data src on s.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              and source_column_physical_name<>business_key_physical_name          
              )
              group by target_column_physical_name  
              """
  cursor.execute(query)
  results = cursor.fetchall()
  for derived_columns in results:
    target_column_name = derived_columns[1]
    transformation_rule = derived_columns[2]
    command = command + f"\t\t{target_column_name}:\n"
    if transformation_rule:
      source_column_list = derived_columns[0]
      command = command + f"\t\t\tvalue: {source_column_list}"      
    else:
      source_column_list = derived_columns[0].split(",")
      for i, source_column in enumerate(source_column_list):
          if i == 0:
            command = command + f"\t\t\tvalue: {source_column}"
          else:
            command += f"||'_'||{source_column}"
    command = command + f"\n\t\t\tdatatype: 'VARCHAR'\n"
  return command


def gen_prejoin_columns(cursor, source):
  
  command = ""  

  source_name, source_object = helper.source_split(source)
  
  query = f"""SELECT 
              COALESCE(l.Prejoin_Target_Column_Alias,l.Prejoin_Extraction_Column_Name) as Prejoin_Target_Column_Name,
              pj_src.Source_Schema_Physical_Name, 
              pj_src.Source_Table_Physical_Name,
              l.Prejoin_Extraction_Column_Name, 
              l.Source_column_physical_name,
              l.Prejoin_Table_Column_Name
              FROM link_entities l
              inner join source_data src on l.Source_Table_Identifier = src.Source_table_identifier
              inner join source_data pj_src on l.Prejoin_Table_Identifier = pj_src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              and l.Prejoin_Table_Identifier is not NULL"""
  
  
  cursor.execute(query)
  prejoined_column_rows = cursor.fetchall()
  for prejoined_column in prejoined_column_rows:

    if command == "":
      command = "prejoined_columns:\n"

    schema = prejoined_column[1]
    table = prejoined_column[2]
    alias = prejoined_column[0]
    bk_column = prejoined_column[3]
    this_column_name = prejoined_column[4]
    ref_column_name = prejoined_column[5]

    command = command + f"""\t{alias}:\n\t\tsrc_schema:"{schema}"\n\t\tsrc_table:"{table}"\n\t\tbk:"{bk_column}"\n\t\tthis_column_name:"{this_column_name}"\n\t\tref_column_name:"{ref_column_name}"\n"""

  return command
  

def generate_stage(cursor, source,generated_timestamp,stage_default_schema, model_path,hashdiff_naming):

  hashed_columns = gen_hashed_columns(cursor, source, hashdiff_naming)
  
  multi_active_config = gen_multi_active_config(cursor, source)

  derived_columns = gen_derived_columns(cursor, source)

  prejoins = gen_prejoin_columns(cursor, source)

  source_name, source_object = helper.source_split(source)
  # print(source_name + ':' + source_object)
  
  model_path = model_path.replace("@@entitytype", "dwh_03_stage").replace("@@SourceSystem", source_name)

  query = f"""SELECT Source_Schema_Physical_Name,Source_Table_Physical_Name, Record_Source_Column, Load_Date_Column, source_object
              FROM source_data src
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'"""
  cursor.execute(query)
  sources = cursor.fetchall()
  for row in sources: #sources usually only has one row
    source_schema_name = row[0]
    source_table_name = row[1] #.replace('_ws_', '_webshop_').replace('_rs_', '_roadshow_')
    target_table_name = row[1].replace('load', 'stg') 
    rs = row[2]
    ldts = row[3]
    timestamp = generated_timestamp
    business_object = row[4]
    condition = "where is_check_ok or rsrc ='SYSTEM'"

    with open(os.path.join(".","templates","stage.txt"),"r") as f:
        command_tmp = f.read()
    f.close()
    command = command_tmp.replace("@@RecordSource",rs).replace("@@LoadDate",ldts).replace("@@HashedColumns", hashed_columns).replace("@@MultiActiveConfig", multi_active_config).replace("@@derived_columns", derived_columns).replace("@@PrejoinedColumns",prejoins).replace('@@SourceName',source_schema_name).replace('@@SourceTable',source_table_name).replace('@@SCHEMA',stage_default_schema)
    command = command.replace("@@where_condition", condition)

    filename = os.path.join(model_path , business_object, f"{target_table_name.lower()}.sql")

    path =os.path.join(model_path, business_object)

    # Check whether the specified path exists or not
    isExist = os.path.exists(path)
    if not isExist:   
    # Create a new directory because it does not exist 
        os.makedirs(path)

    with open(filename, 'w') as f:
      f.write(command.expandtabs(2))

    print(f"Created model \'{target_table_name.lower()}.sql\'")
