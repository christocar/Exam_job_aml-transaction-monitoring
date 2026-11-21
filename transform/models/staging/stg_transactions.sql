with source as (

    select * from {{ source('aml_raw', 'transactions') }}

),

renamed as (

    select
        safe.parse_datetime('%Y/%m/%d %H:%M', `timestamp`)        as transaction_at,
        cast(safe_cast(trim(from_bank) as int64) as string)       as from_bank_id,
        trim(from_account)                                        as from_account_id,
        cast(safe_cast(trim(to_bank) as int64) as string)         as to_bank_id,
        trim(to_account)                                          as to_account_id,
        safe_cast(amount_received as numeric)                     as amount_received,
        trim(receiving_currency)                                  as receiving_currency,
        safe_cast(amount_paid as numeric)                         as amount_paid,
        trim(payment_currency)                                    as payment_currency,
        trim(payment_format)                                      as payment_format,
        case is_laundering
            when '1' then true
            when '0' then false
        end                                                       as is_laundering

    from source

),

hashed as (

    select
        to_hex(md5(to_json_string(renamed))) as row_hash,
        *
    from renamed

)

select
    concat(
        row_hash,
        '-',
        cast(row_number() over (partition by row_hash order by row_hash) as string)
    )                                              as transaction_id,
    * except (row_hash),
    concat(from_bank_id, '|', from_account_id)     as from_account_key,
    concat(to_bank_id, '|', to_account_id)         as to_account_key,
    count(*) over (partition by row_hash) > 1      as is_exact_duplicate

from hashed