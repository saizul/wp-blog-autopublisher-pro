<?php
/**
 * Plugin Name: Register Yoast Meta for REST
 * Description: Exposes Yoast SEO title, meta description and focus keyword to the REST API so wp-blog-autopublisher-pro can set them. Drop into wp-content/mu-plugins/.
 * Author: Saizul Amin
 * License: MIT
 */

defined( 'ABSPATH' ) || exit;

add_action( 'init', function () {
	$keys = array(
		'_yoast_wpseo_title',
		'_yoast_wpseo_metadesc',
		'_yoast_wpseo_focuskw',
	);

	foreach ( $keys as $key ) {
		register_post_meta( 'post', $key, array(
			'type'          => 'string',
			'single'        => true,
			'show_in_rest'  => true,
			'auth_callback' => function () {
				return current_user_can( 'edit_posts' );
			},
		) );
	}
} );
