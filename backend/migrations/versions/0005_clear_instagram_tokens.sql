-- The import job now claims the token (reads and nulls it) when it starts; drop the ones stored before that.
update social_accounts set access_token = null where access_token is not null;
