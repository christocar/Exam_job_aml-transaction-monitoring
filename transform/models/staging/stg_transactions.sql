with source as (

    select * from {{ source('aml_raw', 'transactions') }}

),

renamed as (

    select
        safe.parse_datetime('%Y/%m/%d %H:%M', `timestamp`) as transaction_at,
        trim(from_bank)                                    as from_bank_id,
        trim(from_account)                                 as from_account_id,
        trim(to_bank)                                      as to_bank_id,
        trim(to_account)                                   as to_account_id,
        safe_cast(amount_received as numeric)              as amount_received,
        trim(receiving_currency)                           as receiving_currency,
        safe_cast(amount_paid as numeric)                  as amount_paid,
        trim(payment_currency)                             as payment_currency,
        trim(payment_format)                               as payment_format,
        case is_laundering
            when '1' then true
            when '0' then false
        end                                                as is_laundering

    from source

)

select * from renamed