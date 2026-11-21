with source as (

    select * from {{ source('aml_raw', 'accounts') }}

),

renamed as (

    select
        trim(account_number)                                  as account_id,
        cast(safe_cast(trim(bank_id) as int64) as string)     as bank_id,
        trim(bank_name)                                       as bank_name,
        trim(entity_id)                                       as entity_id,
        trim(entity_name)                                     as entity_name,
        trim(regexp_extract(entity_name, r'^([^#]+)'))        as entity_type

    from source

)

select
    concat(bank_id, '|', account_id) as account_key,
    *
from renamed