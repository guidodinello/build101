-- The import job now deletes the token after its one read; drop the ones stored before that.
update social_accounts set access_token = null where access_token is not null;
