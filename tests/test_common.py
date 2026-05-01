from scripts.common import PostRecord


def test_post_record_defaults():
    post = PostRecord(post_id="20260501-test")
    assert post.status == "idea"
    assert post.ai_tells_check_passed is False
